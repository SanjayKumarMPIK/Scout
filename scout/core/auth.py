"""Secure API key storage using OS credential manager."""

import keyring

SERVICE_NAME = "ScoutAI"

def set_api_key(provider_name: str, key: str) -> None:
    """Store the API key securely."""
    keyring.set_password(SERVICE_NAME, provider_name.lower(), key)

def get_api_key(provider_name: str) -> str | None:
    """Retrieve the API key from secure storage."""
    return keyring.get_password(SERVICE_NAME, provider_name.lower())

def delete_api_key(provider_name: str) -> bool:
    """Delete the API key from secure storage."""
    try:
        keyring.delete_password(SERVICE_NAME, provider_name.lower())
        return True
    except keyring.errors.PasswordDeleteError:
        return False

def prompt_secret(prompt: str) -> str:
    """Prompt for a secret value. Uses plain input().

    The key will be briefly visible in the terminal while typing.
    It is immediately stored in Windows Credential Manager and
    never logged, printed, or sent to the AI model.
    """
    print(prompt, end="", flush=True)
    try:
        return input().strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""
