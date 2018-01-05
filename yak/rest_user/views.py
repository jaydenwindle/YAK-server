import base64
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from rest_framework import viewsets, generics, status, views
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import list_route
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from yak.rest_core.permissions import IsOwnerOrReadOnly
from yak.rest_user.permissions import IsAuthenticatedOrCreate
from yak.rest_user.serializers import SignUpSerializer, LoginSerializer, PasswordChangeSerializer, UserSerializer, \
    PasswordResetSerializer, PasswordSetSerializer
from yak.rest_user.utils import reset_password


User = get_user_model()


class SignUp(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignUpSerializer
    permission_classes = (IsAuthenticatedOrCreate,)


class Login(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = LoginSerializer
    authentication_classes = (BasicAuthentication,)

    def get_queryset(self):
        queryset = super(Login, self).get_queryset()
        return queryset.filter(pk=self.request.user.pk)


class SignIn(views.APIView):
    """
    Same function as `Login` but doesn't use basic auth. This is for web clients,
    so we don't see a browser popup for basic auth.
    """
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        if 'username' not in request.data:
            msg = 'Username required'
            raise AuthenticationFailed(msg)
        elif 'password' not in request.data:
            msg = 'Password required'
            raise AuthenticationFailed(msg)

        user = authenticate(username=request.data['username'], password=request.data['password'])
        if user is None or not user.is_active:
            raise AuthenticationFailed('Invalid username or password')
        serializer = LoginSerializer(instance=user)
        return Response(serializer.data, status=200)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsOwnerOrReadOnly,)
    search_fields = ('username', 'fullname')

    @list_route(methods=["get"])
    def me(self, request):
        if request.user.is_authenticated:
            serializer = self.get_serializer(instance=request.user)
            return Response(serializer.data)
        else:
            return Response({"errors": "User is not authenticated"}, status=status.HTTP_400_BAD_REQUEST)


class PasswordChangeView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, *args, **kwargs):
        if not request.user.check_password(base64.decodebytes(bytes(request.data['old_password'], 'utf8'))):
            raise AuthenticationFailed("Old password was incorrect")
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.data['password'])
        request.user.save()
        return Response({'status': 'password set'})


class PasswordResetView(views.APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_password(request, serializer.data['email'])
        return Response({'status': 'password reset'})


class PasswordSetView(views.APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = PasswordSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid = urlsafe_base64_decode(serializer.data['uid'])
            user = User._default_manager.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, serializer.data['token']):
            user.set_password(serializer.data['password'])
            user.save()
            return Response(UserSerializer(instance=user, context={'request': request}).data)
        else:
            return Response({"errors": "Password reset unsuccessful"}, status=status.HTTP_400_BAD_REQUEST)
