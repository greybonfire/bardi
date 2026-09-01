from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_admin_login(self) -> None:
        response = self.client.get(reverse("admin:index"))

        self.assertRedirects(
            response,
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
        )

    def test_active_non_staff_user_cannot_enter_admin(self) -> None:
        user_model = get_user_model()
        user_model.objects.create_user(
            username="ordinary",
            password="ordinary-password",
            is_active=True,
            is_staff=False,
        )

        self.assertTrue(self.client.login(username="ordinary", password="ordinary-password"))
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    def test_active_staff_user_can_enter_admin(self) -> None:
        user_model = get_user_model()
        user_model.objects.create_user(
            username="staff",
            password="staff-password",
            is_active=True,
            is_staff=True,
        )

        self.assertTrue(self.client.login(username="staff", password="staff-password"))
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site administration")
