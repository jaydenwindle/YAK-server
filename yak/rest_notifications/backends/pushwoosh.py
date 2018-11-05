import json
import requests
from pypushwoosh import client, constants as pushwoosh_constants
from pypushwoosh.command import RegisterDeviceCommand

from yak.settings import yak_settings
from yak.rest_notifications.exceptions import DeviceRegistrationException, NotificationDeliveryException
from yak.rest_notifications import constants


def submit_to_pushwoosh(request_data):
    url = 'https://cp.pushwoosh.com/json/1.3/createMessage'
    response = requests.post(url, data=request_data, headers=client.PushwooshClient.headers)
    return response.json()


class PushwooshNotificationBackend(object):
    """
    Handles push notification sending and device registration via Pushwoosh
    """

    @classmethod
    def register_device(cls, token, hwid, platform, language, **kwargs):
        push_client = client.PushwooshClient()

        platform_code = pushwoosh_constants.PLATFORM_IOS
        if platform == constants.PLATFORM_ANDROID:
            platform_code = pushwoosh_constants.PLATFORM_ANDROID

        command = RegisterDeviceCommand(yak_settings.PUSHWOOSH_APP_CODE, hwid, platform_code,
                                        token, language)

        response = push_client.invoke(command)

        if response["status_code"] != 200:
            raise DeviceRegistrationException("Authentication with Pushwoosh notification service failed", response)

        return response

    @classmethod
    def send_push_notification(cls, receiver, message, deep_link=None, **kwargs):
        notification_data = {
            'content': message,
            'send_date': pushwoosh_constants.SEND_DATE_NOW,
            'devices': [token.token for token in receiver.pushwoosh_tokens.all()],
            'ios_badges': '+1'
        }

        if deep_link is not None:
            notification_data['minimize_link'] = 0
            notification_data['link'] = deep_link

        request = {'request': {
            'notifications': [notification_data],
            'auth': yak_settings.PUSHWOOSH_AUTH_TOKEN,
            'application': yak_settings.PUSHWOOSH_APP_CODE
        }}

        request_data = json.dumps(request)

        response = submit_to_pushwoosh(request_data)

        if response["status_code"] != 200:
            raise NotificationDeliveryException("Notification delivery via Pushwoosh failed", response)

        return response
