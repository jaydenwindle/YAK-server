from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.module_loading import import_string

from yak.settings import yak_settings


def register_device(token, hwid, platform, language, **kwargs):
    notification_backend = import_string(yak_settings.PUSH_NOTIFICATION_BACKEND)
    return notification_backend.register_device(token, hwid, platform, language, **kwargs)


def send_push_notification(receiver, message, deep_link=None, **kwargs):
    notification_backend = import_string(yak_settings.PUSH_NOTIFICATION_BACKEND)
    return notification_backend.send_push_notification(receiver, message, deep_link, **kwargs)


def send_email_notification(receiver, message, reply_to=None):
    headers = {}
    if reply_to:
        headers['Reply-To'] = reply_to

    text_content = strip_tags(message)
    msg = EmailMultiAlternatives(yak_settings.EMAIL_NOTIFICATION_SUBJECT, text_content, settings.DEFAULT_FROM_EMAIL,
                                 [receiver.email], headers=headers)
    msg.attach_alternative(message, "text/html")
    msg.send()
