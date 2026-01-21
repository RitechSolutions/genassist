import os
import json
import base64
import logging
from google.cloud import recaptchaenterprise_v1
from google.oauth2 import service_account


logger = logging.getLogger(__name__)

RECAPTCHA_ACTION = "genassist_chat"


def verify_recaptcha_token(token: str | None) -> tuple[bool, float, str]:
    """
    Verify a reCAPTCHA Enterprise token.

    Args:
        token: The reCAPTCHA token from the frontend.

    Returns:
        Tuple of (is_valid, score, reason).
        - is_valid: True if token passes verification.
        - score: The risk score (0.0 = bot, 1.0 = human).
        - reason: Description of why verification failed (if applicable).
    """
    recaptcha_enabled = os.environ.get("RECAPTCHA_ENABLED")
    recaptcha_project_id = os.environ.get("RECAPTCHA_PROJECT_ID")
    recaptcha_site_key = os.environ.get("RECAPTCHA_SITE_KEY")
    recaptcha_min_score = os.environ.get("RECAPTCHA_MIN_SCORE")
    recaptcha_min_score = float(
        recaptcha_min_score) if recaptcha_min_score is not None else 0.5
    gcp_svc_account_base64 = os.environ.get("GCP_SVC_ACCOUNT")

    if gcp_svc_account_base64 is not None:
        base64_bytes = gcp_svc_account_base64.encode("ascii")
        gcp_svc_account_dict = json.loads(
            base64.b64decode(base64_bytes).decode("utf-8"))
    else:
        gcp_svc_account_dict = None

    if not recaptcha_enabled:
        return True, 1.0, "reCAPTCHA disabled"

    if not recaptcha_project_id or not recaptcha_site_key:
        logger.warning(
            "reCAPTCHA enabled but PROJECT_ID or SITE_KEY not configured")
        return True, 1.0, "reCAPTCHA not configured"

    if not token:
        return False, 0.0, "No reCAPTCHA token provided"

    try:
        credentials = service_account.Credentials.from_service_account_info(
            gcp_svc_account_dict)
        client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient(
            credentials=credentials)

        event = recaptchaenterprise_v1.Event()
        event.site_key = recaptcha_site_key
        event.token = token

        assessment = recaptchaenterprise_v1.Assessment()
        assessment.event = event

        project_name = f"projects/{recaptcha_project_id}"

        request = recaptchaenterprise_v1.CreateAssessmentRequest()
        request.assessment = assessment
        request.parent = project_name

        response = client.create_assessment(request)

        # Check if token is valid
        if not response.token_properties.valid:
            reason = str(response.token_properties.invalid_reason)
            logger.warning(f"reCAPTCHA token invalid: {reason}")
            return False, 0.0, f"Invalid token: {reason}"

        # Check if the action matches
        if response.token_properties.action != RECAPTCHA_ACTION:
            logger.warning(
                f"reCAPTCHA action mismatch: expected '{RECAPTCHA_ACTION}', "
                f"got '{response.token_properties.action}'"
            )
            return False, 0.0, "Action mismatch"

        score = response.risk_analysis.score
        logger.info(f"reCAPTCHA score: {score}")

        # Check if score meets threshold
        if score < recaptcha_min_score:
            reasons = [str(r) for r in response.risk_analysis.reasons]
            logger.warning(
                f"reCAPTCHA score too low: {score}, reasons: {reasons}")
            return False, score, f"Score too low: {score}"

        return True, score, "Verified"

    except Exception as e:
        logger.exception(f"reCAPTCHA verification error: {e}")
        # Fail open to not block users if reCAPTCHA service is down
        return True, 0.5, f"Verification error: {str(e)}"
