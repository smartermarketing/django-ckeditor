from __future__ import absolute_import

import os
import urllib, cStringIO
from io import BytesIO
from ckeditor_uploader import utils
from django.core.files.uploadedfile import InMemoryUploadedFile
from basics.utils import CloudContainer, retry

try:
    from PIL import Image, ImageOps
except ImportError:
    import Image
    import ImageOps


THUMBNAIL_SIZE = (75, 75)


def create_thumbnail(file_path):
    thumbnail_filename = utils.get_thumb_filename(os.path.basename(file_path))
    thumbnail_format = utils.get_image_format(os.path.splitext(file_path)[1])
    file_format = thumbnail_format.split('/')[1]

    image_from_url = cStringIO.StringIO(urllib.urlopen(file_path).read())
    image = Image.open(image_from_url)

    # Convert to RGB if necessary
    # Thanks to Limodou on DjangoSnippets.org
    # http://www.djangosnippets.org/snippets/20/
    if image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')

    # scale and crop to thumbnail
    imagefit = ImageOps.fit(image, THUMBNAIL_SIZE, Image.ANTIALIAS)
    thumbnail_io = BytesIO()
    imagefit.save(thumbnail_io, format=file_format)

    thumbnail = InMemoryUploadedFile(
        thumbnail_io,
        None,
        thumbnail_filename,
        thumbnail_format,
        len(thumbnail_io.getvalue()),
        None)
    thumbnail.seek(0)

    cc = CloudContainer('mediaplan-images')
    data = thumbnail.read()
    cc.upload_data(filename=thumbnail_filename, data=data)
    return thumbnail_filename

def should_create_thumbnail(file_path):
    image_from_url = cStringIO.StringIO(urllib.urlopen(file_path).read())
    try:
        Image.open(image_from_url)
    except IOError:
        return False
    else:
        return utils.is_valid_image_extension(file_path)


def image_verify(f):
    try:
        Image.open(f).verify()
    except IOError:
        raise utils.NotAnImageException
