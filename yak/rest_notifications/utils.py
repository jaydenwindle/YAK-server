import json

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.module_loading import import_string
from pypushwoosh import constants
from pypushwoosh.client import PushwooshClient

from yak.settings import yak_settings


def send_push_notification(receiver, message, deep_link=None):
    notification_backend = import_string(yak_settings.PUSH_NOTIFICATION_BACKEND)
    return notification_backend.send_push_notification(receiver, message, deep_link=None)


def send_email_notification(receiver, message, reply_to=None):
    headers = {}
    if reply_to:
        headers['Reply-To'] = reply_to

    text_content = strip_tags(message)
    msg = EmailMultiAlternatives(yak_settings.EMAIL_NOTIFICATION_SUBJECT, text_content, settings.DEFAULT_FROM_EMAIL,
                                 [receiver.email], headers=headers)
    msg.attach_alternative(message, "text/html")
    msg.send()
