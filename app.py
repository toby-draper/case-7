
import mimetypes
import datetime as dt

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient, ContentSettings

# --- Config ---
AZURE_STORAGE_CONNECTION_STRING = 'DefaultEndpointsProtocol=https;AccountName=urc9sxcasetusy07;AccountKey=YkBt77eUM/Aaj2ZLP3tGE5GR/ZPdarkB8hnlTO/0qgQr/2EKRdKa7hq69X8+xInaNwRYsB2bXLE5+AStyfJWHA==;EndpointSuffix=core.windows.net'
CONTAINER_NAME = 'lanternfly-images'  # Container for lanternfly images
STORAGE_ACCOUNT_NAME = 'urc9sxcasetusy07'  # Storage account name
MAX_FILE_SIZE_MB = 10  # Maximum file size: 10 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024  # enforce size limit (10 MB)

# Initialize Blob service and ensure container exists
bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = bsc.get_container_client(CONTAINER_NAME)
try:
    container_client.create_container()
except Exception:
    # It's fine if it already exists
    pass

# --- Helpers ---
def _is_image_file(filename: str) -> bool:
    """Check if the file is an image based on content type."""
    ctype, _ = mimetypes.guess_type(filename)
    return ctype and ctype.startswith('image/')

def _make_blob_name(filename: str) -> str:
    """Sanitize filename and prepend ISO timestamp."""
    safe = secure_filename(filename)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{safe}" if safe else f"{timestamp}-upload"

def _get_blob_url(blob_name: str) -> str:
    """Get the public URL for a blob."""
    # Use storage account name from config
    return f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"

# --- API Routes ---

@app.post("/api/v1/upload")
def upload():
    """Upload an image to Azure Blob Storage."""
    # Check if file exists in request
    if "file" not in request.files:
        return jsonify(ok=False, error="No file provided"), 400
    
    file = request.files["file"]
    if not file.filename:
        return jsonify(ok=False, error="No file selected"), 400
    
    # Check if file is an image
    if not _is_image_file(file.filename):
        return jsonify(ok=False, error="Only image files are allowed"), 400
    
    # Create blob name with timestamp
    blob_name = _make_blob_name(file.filename)
    blob_client = container_client.get_blob_client(blob_name)
    
    # Set content type
    ctype, _ = mimetypes.guess_type(file.filename)
    content_settings = ContentSettings(content_type=ctype or "application/octet-stream")
    
    try:
        # Upload to blob storage (allow overwrite)
        blob_client.upload_blob(
            file.stream,
            overwrite=True,
            content_settings=content_settings,
        )
        
        # Return success with URL
        url = _get_blob_url(blob_name)
        return jsonify(ok=True, url=url), 200
    
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/api/v1/gallery")
def gallery():
    """Return a list of all uploaded images."""
    try:
        gallery_urls = []
        for blob in container_client.list_blobs():
            url = _get_blob_url(blob.name)
            gallery_urls.append(url)
        
        return jsonify(ok=True, gallery=gallery_urls), 200
    
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/api/v1/health")
def health():
    """Health check endpoint."""
    return jsonify(ok=True, status="healthy"), 200



@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
