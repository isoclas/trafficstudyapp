import os
import logging
from flask import current_app
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

def init_cloudinary():
    """Initialize Cloudinary configuration"""
    if current_app.config.get('USE_CLOUDINARY'):
        cloudinary.config(
            cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
            api_key=current_app.config['CLOUDINARY_API_KEY'],
            api_secret=current_app.config['CLOUDINARY_API_SECRET']
        )
        logging.info("Cloudinary initialized")

def upload_file(file, folder="uploads"):
    """Upload file to Cloudinary or local storage"""
    if not file or file.filename == '':
        return None, "No file selected"
    
    filename = secure_filename(file.filename)
    
    if current_app.config.get('USE_CLOUDINARY'):
        try:
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                public_id=f"{folder}/{filename}",
                resource_type="raw"  # For non-image files
            )
            return result['secure_url'], None
        except Exception as e:
            logging.error(f"Cloudinary upload failed: {e}")
            return None, f"Upload failed: {str(e)}"
    else:
        # Local storage fallback
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        file.save(upload_path)
        return upload_path, None

def download_file(file_url_or_path):
    """Download file from Cloudinary or local storage"""
    if current_app.config.get('USE_CLOUDINARY') and file_url_or_path.startswith('http'):
        # Return Cloudinary URL directly
        return file_url_or_path
    else:
        # Local file path
        return file_url_or_path

def delete_file(file_url_or_path):
    """Delete file from Cloudinary or local storage"""
    if current_app.config.get('USE_CLOUDINARY') and file_url_or_path.startswith('http'):
        try:
            # Extract public_id from Cloudinary URL
            public_id = file_url_or_path.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(public_id, resource_type="raw")
            return True
        except Exception as e:
            logging.error(f"Cloudinary delete failed: {e}")
            return False
    else:
        # Local file deletion
        try:
            if os.path.exists(file_url_or_path):
                os.remove(file_url_or_path)
            return True
        except Exception as e:
            logging.error(f"Local file delete failed: {e}")
            return False