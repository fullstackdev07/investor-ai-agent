def get_initial_outreach_email(investor_name: str, founder_name: str, founder_startup_name: str, startup_pitch: str, agent_name: str = "AI Assistant", investor_focus: str = "your area of interest") -> dict:
    """ Formats the initial outreach email template. """
    subject = f"Introduction: {founder_startup_name} - Exploring Investment Synergy"
    body = f"""
Dear {investor_name},

My name is {agent_name}, and I'm assisting {founder_name}, the founder of {founder_startup_name}.

{founder_startup_name} is working on {startup_pitch}. We noted your interest in {investor_focus} and thought there might be a potential fit based on our data. # <<< CHANGE wording as desired

Would you be open to a brief introductory call with {founder_name} to learn more?

Best regards,

{agent_name} # <<< CHANGE signature if needed
"""
    return {"subject": subject, "body": body.strip()}


def get_follow_up_cc_email(investor_name: str, founder_name: str, founder_startup_name: str, agent_name: str = "AI Assistant") -> dict:
    """ Formats the follow-up email to CC both parties. """
    subject = f"Re: Introduction: {founder_startup_name} - Connecting You Both"
    body = f"""
Great!

{investor_name} and {founder_name} - connecting you both as requested.

{founder_name}, {investor_name} has expressed interest in learning more. Please feel free to coordinate directly to find a suitable time.

Best regards,

{agent_name} # <<< CHANGE signature if needed
"""
    return {"subject": subject, "body": body.strip()}