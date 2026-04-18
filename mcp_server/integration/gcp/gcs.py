"""GCP: Contains functions that connect to Google Cloud."""
from google.cloud import storage
import os
import logging

logger = logging.getLogger()

# GCS
gcs_client = storage.Client()

def upload_to_gcs(bucket_name:str, path: str)->None:
    """Uploads blob objects to GCS.
    Args: 
        bucket_name (str): Bucket name to upload documents.
        path (str): Directory contianing the blobs to upload.
    Retruns: 
        None.
    """
    bucket = gcs_client.bucket(bucket_name)

    for root, dirs, files in os.walk(path):
        for f in files:
            local_path = os.path.join(root,f)
            blob_path = local_path.replace(path, "") # strip local prefix
            bucket.blob(blob_path).upload_from_filename(local_path)
            logger.info(f"Uploaded {blob_path}.")
