
class BaseNotificationBackend(object):
    """
    The base class for notification backends.
    """

    @classmethod
    def register_device(token, hwid, platform, language, **kwargs):
        """
        Handles saving the device token and registering it with the third party service.

        Args:
            token (string): The notifcation token received to register
            hwid (string): The unique hardware id of the device being registered
            platform (string): One of constants.PLATFORM_IOS or constants.PLATFORM_ANDROID
            language (string): The language of the receiving user

        Returns:
            dict: raw response from the third party service

        Raises:
            DeviceRegistrationException: if an error occurs while registering the device
            with the third party service
        """
        raise NotImplementedError("Notification backends must define the register_device method")

    @classmethod
    def send_push_notification(user, message, deep_link=None, **kwargs):
        """
        Handles sending the push notification to the third party service.

        Args:
            user (USER_MODEL instance): The user receiving the notifcation
            message (string): The message content to send to the user
            deep_link (string): A deep link to send along with the notification

        Returns:
            dict: raw response from the third party service

        Raises:
            NotificationDeliveryException: if an error occurs while sending the
            notification via the third party service
        """
        raise NotImplementedError("Notification backends must define the send_push_notification method")
