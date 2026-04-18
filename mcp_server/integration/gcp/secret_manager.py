from google.cloud import secretmanager

def load_secret(name:str) -> bytes:
    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/porygon-legaldoc-cuad/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data
