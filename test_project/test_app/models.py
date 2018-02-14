from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.sites.models import Site
from django.db import models
from django.db.models.signals import post_save
from django.utils.baseconv import base62
from yak.rest_core.models import resize_model_photos, CoreModel
from yak.rest_notifications.models import create_notification_settings, Notification
from yak.rest_social_network.models import FollowableModel, BaseSocialModel, Like, Flag, Share, Tag, \
    Comment, relate_tags, mentions, AbstractSocialYeti
from yak.rest_user.utils import create_auth_client


class User(AbstractSocialYeti):
    notifications = GenericRelation(Notification)

    class Meta:
        ordering = ['-username']

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        resize_model_photos(self)
        super(User, self).save(force_insert=False, force_update=False, using=None, update_fields=None)


FollowableModel.register(User)

post_save.connect(create_auth_client, sender=User)
post_save.connect(create_notification_settings, sender=User)


class Post(BaseSocialModel):
    user = models.ForeignKey(User, related_name='posts', on_delete=models.CASCADE)
    title = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="post_photos/thumbnail/", blank=True, null=True)

    TAG_FIELD = 'description'

    likes = GenericRelation(Like)
    flags = GenericRelation(Flag)
    shares = GenericRelation(Share)
    related_tags = models.ManyToManyField(Tag, blank=True)
    comments = GenericRelation(Comment)
    notifications = GenericRelation(Notification)

    def likes_count(self):
        return self.likes.count()

    def comments_count(self):
        return self.comments.count()

    def identifier(self):
        return "{}".format(self.title)

    def __unicode__(self):
        return "{}".format(self.title) if self.title else "Untitled"

    def url(self):
        current_site = Site.objects.get_current()
        return "http://{0}/{1}/{2}/".format(current_site.domain, "post", base62.encode(self.pk))

    def facebook_og_info(self):
        return {'action': 'post', 'object': 'cut', 'url': self.url()}

    def create_social_message(self, provider):
        message = "{} published by {} on Test Project".format(self.title, self.user.username)

        # TODO: Sending of messages to post on social media is broken and convoluted at this point, need to refactor
        if provider == "twitter":
            return "{}".format(message.encode('utf-8'))
        else:
            return "{} {}".format(message.encode('utf-8'), self.url())


post_save.connect(relate_tags, sender=Post)
post_save.connect(mentions, sender=Post)


class Article(CoreModel):
    title = models.CharField(max_length=60)
    body = models.TextField()
    thumbnail = models.ImageField(upload_to="article_photos/thumbnail/", blank=True, null=True)
    likes = GenericRelation(Like)
    notifications = GenericRelation(Notification)

    def __unicode__(self):
        return "{}".format(self.title) if self.title else "Untitled"

    def identifier(self):
        return "{}".format(self.title)
