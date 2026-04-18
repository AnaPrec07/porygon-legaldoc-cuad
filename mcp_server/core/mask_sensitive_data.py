
import google.cloud.dlp_v2 as dlp_v2
from google.cloud.dlp_v2 import types as dlp_types
import base64
from mcp_server.integration.gcp.secret_manager import load_secret

class MaskSensitiveData():
    def __init__(self):
        self.builtin_infotypes = [
            "PERSON_NAME",
            "DATE_OF_BIRTH",
            "AGE",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "STREET_ADDRESS",
            "LOCATION",
            "US_SOCIAL_SECURITY_NUMBER",
            "US_PASSPORT",
            "US_DRIVERS_LICENSE_NUMBER",
            "US_HEALTHCARE_NPI",
            "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER",
            "MEDICAL_RECORD_NUMBER",
            "US_MEDICARE_BENEFICIARY_ID_NUMBER",
            "DATE",
            "IP_ADDRESS",
        ]
        self.project_id = "porygon-legaldoc-cuad"
        self.location ="global"
        self.kms_key_name = f"projects/{self.project_id}/locations/{self.location}/keyRings/dlp-keyring/cryptoKeys/dlp-key"
        self.wrapped_key = base64.b64decode(load_secret(name="kms_wrapped_key"))

        
    def _build_crypto_replace_config(
        self,
    ) -> dlp_types.DeidentifyConfig:
        """Build a DeidentifyConfig using CryptoDeterministicConfig with a KMS-wrapped key.

        CryptoDeterministicConfig produces consistent tokens for the same plaintext,
        which allows downstream correlation (e.g. the same patient name always maps
        to the same token) while keeping values unreadable without the KMS key.

        Args:
            kms_key_name: Full resource name of the Cloud KMS key used to wrap the
                data encryption key, e.g.
                "projects/{project_id}/locations/{location}/keyRings/RING/cryptoKeys/KEY"
            wrapped_key: AES-256 key encrypted (wrapped) with the KMS key above.

        Returns:
            A fully populated DeidentifyConfig proto.
        """
        kms_wrapped_key = dlp_types.KmsWrappedCryptoKey(
            wrapped_key=self.wrapped_key,
            crypto_key_name=self.kms_key_name,
        )
        crypto_key = dlp_types.CryptoKey(kms_wrapped=kms_wrapped_key)

        crypto_config = dlp_types.CryptoDeterministicConfig(
            crypto_key=crypto_key,
            # Preserve the surrogate type so re-identification is possible later.
            surrogate_info_type=dlp_types.InfoType(name="DEIDENTIFIED"),
        )

        primitive_transformation = dlp_types.PrimitiveTransformation(
            crypto_deterministic_config=crypto_config,
        )

        info_type_transformations = dlp_types.InfoTypeTransformations(
            transformations=[
                dlp_types.InfoTypeTransformations.InfoTypeTransformation(
                    info_types=[],  # Empty = apply to all detected info types
                    primitive_transformation=primitive_transformation,
                )
            ]
        )

        return dlp_types.DeidentifyConfig(
            info_type_transformations=info_type_transformations
        )

    def deidentify_text(
        self,
        text: str,
    ) -> str:
        
        """Mask sensitive PHI/PII in *text* using GCP DLP with a KMS-wrapped key.

        Args:
            text: Raw document text extracted from a healthcare record.

        Returns:
            The de-identified text with all detected sensitive values replaced by
            opaque tokens prefixed with ``[DEIDENTIFIED]``.

        Raises:
            google.api_core.exceptions.GoogleAPICallError: On DLP API errors.
            ValueError: If *text* is empty.
        """
        if not text or not text.strip():
            raise ValueError("text must be a non-empty string")

        selected_info_types = self.builtin_infotypes

        client = dlp_v2.DlpServiceClient()
        parent = f"projects/{self.project_id}/locations/{self.location}"

        # --- Inspect config: what to look for ---
        inspect_config = dlp_types.InspectConfig(
            info_types=[dlp_types.InfoType(name=t) for t in selected_info_types],
            min_likelihood=dlp_types.Likelihood.POSSIBLE,
            include_quote=False,
        )

        # --- Deidentify config: how to replace it ---
        deidentify_config = self._build_crypto_replace_config()

        # --- Content item ---
        item = dlp_types.ContentItem(value=text)

        request = dlp_types.DeidentifyContentRequest(
            parent=parent,
            inspect_config=inspect_config,
            deidentify_config=deidentify_config,
            item=item,
        )

        response = client.deidentify_content(request=request)
        return response.item.value
    
    def reidentify_text(
        self,
        masked_text: str,
    ) -> str:
        """Reverse the de-identification produced by :func:`deidentify_text`.

        Uses the same KMS-wrapped key so that ``[DEIDENTIFIED]`` surrogate tokens
        are mapped back to their original plaintext values.

        Args:
            masked_text: Text containing ``[DEIDENTIFIED]`` surrogate tokens.

        Returns:
            Text with surrogate tokens replaced by original plaintext values.

        Raises:
            google.api_core.exceptions.GoogleAPICallError: On DLP API errors.
        """
        client = dlp_v2.DlpServiceClient()
        parent = f"projects/{self.project_id}/locations/global"

        kms_wrapped_key = dlp_types.KmsWrappedCryptoKey(
            wrapped_key=self.wrapped_key,
            crypto_key_name=self.kms_key_name,
        )
        crypto_key = dlp_types.CryptoKey(kms_wrapped=kms_wrapped_key)

        crypto_config = dlp_types.CryptoDeterministicConfig(
            crypto_key=crypto_key,
            surrogate_info_type=dlp_types.InfoType(name="DEIDENTIFIED"),
        )

        primitive_transformation = dlp_types.PrimitiveTransformation(
            crypto_deterministic_config=crypto_config,
        )
        reidentify_config = {
            "info_type_transformations": {
                "transformations": [
                    {
                        "primitive_transformation": primitive_transformation,
                        "info_types":[dlp_types.InfoType(name="DEIDENTIFIED")],
                    }
                ]
            }
        }

        # Inspect for the surrogate type so DLP knows where to look
        inspect_config = dlp_types.InspectConfig(
            custom_info_types=[
                dlp_types.CustomInfoType(
                    info_type=dlp_types.InfoType(name="DEIDENTIFIED"),
                    surrogate_type=dlp_types.CustomInfoType.SurrogateType(),
                )
            ]
        )

        item = dlp_types.ContentItem(value=masked_text)

        request = dlp_types.ReidentifyContentRequest(
            parent=parent,
            reidentify_config=reidentify_config,
            inspect_config=inspect_config,
            item=item,
        )

        response = client.reidentify_content(request=request)
        return response.item.value
