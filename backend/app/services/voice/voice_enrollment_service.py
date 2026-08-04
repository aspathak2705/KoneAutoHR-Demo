class VoiceEnrollmentService:
    async def enroll_voice(self, *args, **kwargs):
        raise RuntimeError("Voice enrollment is not available in the rollback flow.")

voice_enrollment_service = VoiceEnrollmentService()
