from django.shortcuts import redirect
from django.utils.timezone import now

class AutoLogoutMiddleware:
    """Middleware to auto logout users after 5 minutes of inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get("user_id"):
            last_activity = request.session.get("last_activity")

            if last_activity:
                last_activity_time = float(last_activity)
                current_time = now().timestamp()
                inactivity_duration = current_time - last_activity_time  # Time in seconds

                if inactivity_duration > 300:  # 5 minutes = 300 seconds
                    request.session.flush()  # Clear session (Logout)
                    return redirect("login_view")  # Redirect to login

            # ✅ Update last activity timestamp
            request.session["last_activity"] = now().timestamp()

        response = self.get_response(request)
        return response
