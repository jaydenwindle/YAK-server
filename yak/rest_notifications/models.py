from collections import defaultdict
from caching.base import CachingMixin, CachingManager
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import models
from django.template.loader import render_to_string
from celery.task import task
from yak.rest_core.models import CoreModel
from yak.settings import yak_settings


class NotificationType(CachingMixin, CoreModel):
    name = models.CharField(max_length=32)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    objects = CachingManager()

    def __unicode__(self):
        return "{}".format(self.name)


class NotificationSetting(CoreModel):
    notification_type = models.ForeignKey(NotificationType, related_name="user_settings", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='notification_settings', on_delete=models.CASCADE)
    allow_push = models.BooleanField(default=True)
    allow_email = models.BooleanField(default=True)

    class Meta:
        unique_together = ('notification_type', 'user')
        ordering = ['-created']

    def __unicode__(self):
        return "{}: {}".format(self.user, self.notification_type)

    def name(self):
        return "{}: {}".format(self.user, self.notification_type)


def create_notification_settings(sender, **kwargs):
    sender_name = "{0}.{1}".format(sender._meta.app_label, sender._meta.object_name)
    if sender_name.lower() != settings.AUTH_USER_MODEL.lower():
        return

    if kwargs['created']:
        user = kwargs['instance']
        if not user.notification_settings.exists():
            user_settings = []
            for notification_type in NotificationType.objects.all():
                user_settings.append(NotificationSetting(user=user, notification_type=notification_type))
            NotificationSetting.objects.bulk_create(user_settings)


class Notification(CoreModel):
    PUSH = "push"
    EMAIL = "email"

    notification_type = models.ForeignKey(NotificationType, related_name="notifications", on_delete=models.CASCADE)
    template_override = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications_received", null=True, blank=True,
                             on_delete=models.CASCADE)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications_sent", null=True, blank=True,
                                 on_delete=models.CASCADE)

    # The object that the notification is about, not the social model related to it
    # E.g., if you Like a Post, the content_object for the notification is the Post, not the Like
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey()

    def message(self, location):
        """
        Takes our configured notifications and creates a message
        replacing the appropriate variables from the content object
        """

        data = defaultdict(str)
        # get the domain from Site
        data['domain'] = Site.objects.get_current().domain

        if self.content_object:
            data['identifier'] = self.content_object.identifier()
        if self.reporter:
            data['reporter'] = self.reporter.identifier()

        if hasattr(self.content_object, 'extra_notification_params'):
            data.update(self.content_object.extra_notification_params())

        configured_template_name = "{}.html".format(self.notification_type.slug)
        template_name = self.template_override if self.template_override else configured_template_name
        return render_to_string("notifications/{}/{}".format(location, template_name), data)

    def email_message(self):
        return self.message(Notification.EMAIL)

    def push_message(self):
        message = self.message(Notification.PUSH)
        if self.reporter:
            return "{0} {1}".format(self.reporter, message)
        else:
            return "{0}".format(message)

    @property
    def name(self):
        return "{}".format(self.notification_type)

    def __unicode__(self):
        return "{}: {}".format(self.user, self.notification_type)

    class Meta:
        ordering = ['-created']


@task
def create_notification(receiver, reporter, content_object, notification_type, template_override=None, reply_to=None):
    # If the receiver of this notification is the same as the reporter or
    # if the user has blocked this type, then don't create
    if receiver == reporter:
        return

    notification = Notification.objects.create(user=receiver,
                                               reporter=reporter,
                                               content_object=content_object,
                                               notification_type=notification_type,
                                               template_override=template_override)
    notification.save()

    notification_setting = NotificationSetting.objects.get(notification_type=notification_type, user=receiver)
    if notification_setting.allow_push and yak_settings.ALLOW_PUSH:
        from .utils import send_push_notification
        send_push_notification(receiver, notification.push_message())

    if notification_setting.allow_email and yak_settings.ALLOW_EMAIL and receiver.email:
        from .utils import send_email_notification
        send_email_notification(receiver, notification.email_message(), reply_to=reply_to)


class PushwooshToken(CoreModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="pushwoosh_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=120)
