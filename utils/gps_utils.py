from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def get_exif_data(image_path):
    """
    Extract EXIF metadata from an image file.
    Returns a dictionary of EXIF tags and values.
    """
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data:
            return {}
        # Convert EXIF tag IDs to human-readable names
        return {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
    except Exception as e:
        print(f"[⚠️] Error reading EXIF data: {e}")
        return {}

def get_gps_info(exif):
    """
    Extract GPS latitude and longitude (if present) from EXIF data.
    Returns (latitude, longitude) in decimal degrees, or (None, None) if not found.
    """
    try:
        gps_info = exif.get('GPSInfo')
        if not gps_info:
            return None, None

        gps_data = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}

        def convert_to_degrees(value):
            """Convert GPS coordinates stored as rationals to degrees."""
            d, m, s = value
            return d[0] / d[1] + (m[0] / m[1]) / 60 + (s[0] / s[1]) / 3600

        # Extract and convert coordinates
        lat = convert_to_degrees(gps_data['GPSLatitude'])
        if gps_data.get('GPSLatitudeRef') != 'N':
            lat = -lat

        lon = convert_to_degrees(gps_data['GPSLongitude'])
        if gps_data.get('GPSLongitudeRef') != 'E':
            lon = -lon

        return lat, lon

    except Exception as e:
        print(f"[⚠️] Error extracting GPS info: {e}")
        return None, None
