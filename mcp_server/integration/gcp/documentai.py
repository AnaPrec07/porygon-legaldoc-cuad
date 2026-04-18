"""GCP: Contains functions that connect to Google Cloud Document AI."""

from google.cloud import documentai


docai_client = documentai.DocumentProcessorServiceClient()

def process_document(
    document: bytes,
    mime_type: str = "application/pdf",
    project_id: str="porygon-legaldoc-cuad",
    location: str="us",
    processor_id: str="e5822741a51eeb33",
) -> documentai.Document:
    """Sends a raw document to a Document AI processor and returns the result.

    Args:
        project_id: GCP project ID.
        location: Processor location (e.g. "us" or "eu").
        processor_id: The ID of the pre-trained processor to use.
        document: Raw bytes of the document.
        mime_type: MIME type of the document (e.g. "application/pdf", "image/png").

    Returns:
        A Document AI Document proto containing the extracted text and layout.
    """
    processor_name = docai_client.processor_path(project_id, location, processor_id)
    raw_document = documentai.RawDocument(content=document, mime_type=mime_type)
    request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
    result = docai_client.process_document(request=request)
    return result.document


