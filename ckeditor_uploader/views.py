from __future__ import absolute_import

import os
import string
import random
import logging
from datetime import datetime

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views import generic
from django.views.decorators.csrf import csrf_exempt

from ckeditor_uploader import image_processing
from ckeditor_uploader import utils
from ckeditor_uploader.forms import SearchForm
from basics.utils import CloudContainer, retry

logger = logging.getLogger()


class ImageUploadView(generic.View):
    http_method_names = ['post']

    def post(self, request, **kwargs):
        """
        Uploads a file and send back its URL to CKEditor.
        """
        logger.info("Enter ImageUploadView.post")
        uploaded_file = request.FILES['upload']

        backend = image_processing.get_backend()
        logger.info("ImageUploadView.post _verify_file")
        self._verify_file(backend, uploaded_file)
        logger.info("ImageUploadView.post _verify_file returned")
        saved_name = self._save_file(request, uploaded_file)
        path = getattr(settings, 'CKEDITOR_UPLOAD_PATH', "/uploads")
        url = path + saved_name
        self._create_thumbnail_if_needed(backend, url)
        logger.info("Exit ImageUploadView.post")
        # Respond with Javascript sending ckeditor upload url.
        return HttpResponse("""
        <script type='text/javascript'>
            window.parent.CKEDITOR.tools.callFunction({0}, '{1}');
        </script>""".format(request.GET['CKEditorFuncNum'], url))

    def _verify_file(self, backend, uploaded_file):
        try:
            backend.image_verify(uploaded_file)
        except utils.NotAnImageException:
            return self._on_verification_failure()

    def _on_verification_failure(self):
        pass

    @staticmethod
    def _save_file(request, uploaded_file):
        logger.info("_save_file Enter")
        filename = os.path.splitext(uploaded_file.name)
        logger.info("_save_file 1")
        saved_name = filename[0] + "_" +(''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(6))) + filename[1]
        logger.info("_save_file 2")
        cc = CloudContainer('mediaplan-images')
        logger.info("_save_file cc created")
        uploaded_file.seek(0)
        data = uploaded_file.read()
        logger.info("_save_file calling upload_data")
        cc.upload_data(filename=saved_name, data=data)
        logger.info("_save_file upload_data returned")
        logger.info("_save_file Exit")
        return saved_name
    @staticmethod
    def _create_thumbnail_if_needed(backend, saved_path):
        if backend.should_create_thumbnail(saved_path):
            backend.create_thumbnail(saved_path)

upload = csrf_exempt(ImageUploadView.as_view())


def get_image_files(user=None, path=''):
    """
    Recursively walks all dirs under upload dir and generates a list of
    full paths for each file found.
    """
    # If a user is provided and CKEDITOR_RESTRICT_BY_USER is True,
    # limit images to user specific path, but not for superusers.
    STORAGE_DIRECTORIES = 0
    STORAGE_FILES = 1

    user_path = ''

    browse_path = os.path.join(settings.CKEDITOR_UPLOAD_PATH, user_path, path)

    try:
        storage_list = default_storage.listdir(browse_path)
    except NotImplementedError:
        return
    except OSError:
        return

    for filename in storage_list[STORAGE_FILES]:
        if os.path.splitext(filename)[0].endswith('_thumb') or os.path.basename(filename).startswith('.'):
            continue
        filename = os.path.join(browse_path, filename)
        yield filename

    for directory in storage_list[STORAGE_DIRECTORIES]:
        if directory.startswith('.'):
            continue
        directory_path = os.path.join(path, directory)
        for element in get_image_files(user=user, path=directory_path):
            yield element


def get_files_browse_urls(user=None):
    """
    Recursively walks all dirs under upload dir and generates a list of
    thumbnail and full image URL's for each file found.
    """
    files = []
    for filename in get_image_files(user=user):
        src = utils.get_media_url(filename)
        visible_filename = None
        if getattr(settings, 'CKEDITOR_IMAGE_BACKEND', None):
            if is_image(src):
                thumb = utils.get_media_url(utils.get_thumb_filename(filename))
            else:
                thumb = utils.get_icon_filename(filename)
                visible_filename = os.path.split(filename)[1]
                if len(visible_filename) > 20:
                    visible_filename = visible_filename[0:19] + '...'
        else:
            thumb = src
        files.append({
            'thumb': thumb,
            'src': src,
            'is_image': is_image(src),
            'visible_filename': visible_filename,
        })

    return files


def is_image(path):
    ext = path.split('.')[-1].lower()
    return ext in ['jpg', 'jpeg', 'png', 'gif']


def browse(request):
    files = get_files_browse_urls(request.user)
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            files = filter(lambda d: form.cleaned_data.get('q', '').lower() in d['visible_filename'].lower(), files)
    else:
        form = SearchForm()
    context = RequestContext(request, {
        'files': files,
        'form': form
    })
    return render_to_response('ckeditor/browse.html', context)
