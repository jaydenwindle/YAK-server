import base64
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status, generics
from rest_framework.decorators import detail_route
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from social_django.utils import load_strategy
from social_django.models import UserSocialAuth
from social_django.utils import load_backend
from social_core.backends.oauth import BaseOAuth1, BaseOAuth2
from social_core.backends.utils import get_backend
from social_core.exceptions import AuthAlreadyAssociated
from yak.rest_social_auth.serializers import SocialSignUpSerializer
from yak.rest_social_auth.utils import post_social_media
from yak.rest_user.serializers import UserSerializer
from yak.rest_user.views import SignUp


User = get_user_model()


class SocialSignUp(SignUp):
    serializer_class = SocialSignUpSerializer

    def create(self, request, *args, **kwargs):
        """
        Override `create` instead of `perform_create` to access request
        request is necessary for `load_strategy`
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = request.data['provider']

        # If this request was made with an authenticated user, try to associate this social account with it
        authed_user = request.user if not request.user.is_anonymous else None

        strategy = load_strategy(request)
        backend = load_backend(strategy=strategy, name=provider, redirect_uri=None)

        if isinstance(backend, BaseOAuth1):
            token = {
                'oauth_token': request.data['access_token'],
                'oauth_token_secret': request.data['access_token_secret'],
            }
        elif isinstance(backend, BaseOAuth2):
            token = request.data['access_token']

        try:
            user = backend.do_auth(token, user=authed_user)
        except AuthAlreadyAssociated:
            return Response({"errors": "That social media account is already in use"},
                            status=status.HTTP_400_BAD_REQUEST)

        if user and user.is_active:
            # if the access token was set to an empty string, then save the access token from the request
            auth_created = user.social_auth.get(provider=provider)
            if not auth_created.extra_data['access_token']:
                auth_created.extra_data['access_token'] = token
                auth_created.save()

            # Allow client to send up password to complete auth flow
            if not authed_user and 'password' in request.data:
                password = base64.decodestring(request.data['password'])
                user.set_password(password)
                user.save()

            # Set instance since we are not calling `serializer.save()`
            serializer.instance = user
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            return Response({"errors": "Error with social authentication"}, status=status.HTTP_400_BAD_REQUEST)


class SocialShareMixin(object):

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated])
    def social_share(self, request, pk):
        try:
            user_social_auth = UserSocialAuth.objects.get(user=request.user, provider=request.data['provider'])
            social_obj = self.get_object()
            post_social_media(user_social_auth, social_obj)
            return Response({'status': 'success'})
        except UserSocialAuth.DoesNotExist:
            raise AuthenticationFailed("User is not authenticated with {}".format(request.data['provider']))


class SocialFriends(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        provider = self.request.query_params.get('provider', None)
        user_social_auth = self.request.user.social_auth.filter(provider=provider).first()
        if user_social_auth:  # `.first()` doesn't fail, it just returns None
            backend = get_backend(settings.AUTHENTICATION_BACKENDS, provider)
            friends = backend.get_friends(user_social_auth)
            return friends
        else:
            raise AuthenticationFailed("User is not authenticated with {}".format(provider))
