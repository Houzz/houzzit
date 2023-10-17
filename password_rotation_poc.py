import requests
import json
import time


# Okta Configuration
OKTA_API_TOKEN = "OKTA_API_TOKEN"
OKTA_API_ENDPOINT = "https://<OKTA_DOMAIN>.okta.com"
OKTA_GROUP_ID = "<OKTA_GROUP_ID>"

# 1Password Configuration
ONE_PASSWORD_CONNECT_HOST = "https://<YOUR_CONNECT_SERVER>"
ONE_PASSWORD_VAULT_ID = "<ONE_PASSWORD_VAULT_ID>"
ONE_PASSWORD_TOKEN = "<ONE_PASSWORD_TOKEN>"
ONE_PASSWORD_GENERATED_PASSWORD_LENGTH = 14
ONE_PASSWORD_GENERATED_PASSWORD_CHARACTER_SETS = ["LETTERS", "DIGITS", "SYMBOLS"]

# Headers
OKTA_HEADERS = {
    'Authorization': f'SSWS {OKTA_API_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

ONE_PASSWORD_HEADERS = {
    "Authorization": f"Bearer {ONE_PASSWORD_TOKEN}",
    "Content-Type": "application/json",
}

# Individual functions to call in the main function

# Fetches members of a specific Okta group.
def get_okta_group_members():
    okta_group_url = f'{OKTA_API_ENDPOINT}/api/v1/groups/{OKTA_GROUP_ID}/users'
    try:
        response = requests.get(okta_group_url, headers=OKTA_HEADERS)
        response.raise_for_status()
        return response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException as e:
        print(f'Error fetching Okta group members: {e}')
        return []


# Fetches the item IDs of 1Password items based on the user ID (used as the title).
def fetch_1password_items(user_id):
    one_password_fetch_items_url = f"{ONE_PASSWORD_CONNECT_HOST}/v1/vaults/{ONE_PASSWORD_VAULT_ID}/items"
    try:
        response = requests.get(one_password_fetch_items_url, headers=ONE_PASSWORD_HEADERS)
        response.raise_for_status()
        
        if response.status_code != 200:
            print(f"Request for all items within a vault at 1Password failed with status {response.status_code}")
            return None

        items = response.json()
        for item in items:
            if item['title'] == user_id:
                return item['id']
                
    except requests.exceptions.RequestException as e:
        print(f'Error fetching 1Password items: {e}')
        return None
    return None


# Retrieves details (specifically, the password) of a 1Password item by its item ID.
def retrieve_1password_item_details(item_id):
    one_password_item_details_url = f"{ONE_PASSWORD_CONNECT_HOST}/v1/vaults/{ONE_PASSWORD_VAULT_ID}/items/{item_id}"
    try:
        response = requests.get(one_password_item_details_url, headers=ONE_PASSWORD_HEADERS)
        response.raise_for_status()

        if response.status_code != 200:
            print(f"Request for item details from 1Password failed with status {response.status_code}")
            return None

        item = response.json()

        for field in item['fields']:
            if field['label'] == 'password':
                return field['value']

    except requests.exceptions.RequestException as e:
        print(f'Error retrieving 1Password item details: {e}')
        return None

    print("Password field not found in 1Password item.")
    return None


# Changes the password of a 1Password item.
def change_1password_item_password(item_id):
    one_password_change_password_url = f"{ONE_PASSWORD_CONNECT_HOST}/v1/vaults/{ONE_PASSWORD_VAULT_ID}/items/{item_id}"
    body = [{
        "op": "replace",
        "path": "/fields/password",
        "value": {
            "purpose": "PASSWORD",
            "generate": True,
                "recipe": {
                    "length": ONE_PASSWORD_GENERATED_PASSWORD_LENGTH,
                    "characterSets": ONE_PASSWORD_GENERATED_PASSWORD_CHARACTER_SETS
                }
        }
    }]

    try:
        response = requests.patch(one_password_change_password_url, headers=ONE_PASSWORD_HEADERS, json=body)
        response.raise_for_status()

        if response.status_code != 200:
            print(f"Request to change the password within 1Password item failed with status {response.status_code}")
            return None
        
        print(f"Password updated successfully at 1Password!")
    
    except requests.exceptions.RequestException as e:
        print(f'Error updating 1Password item password: {e}')
        return None


# Creates a new 1Password item for the given user ID and email.
def create_new_1password_item(user_id, email):
    one_password_create_item_url = f"{ONE_PASSWORD_CONNECT_HOST}/v1/vaults/{ONE_PASSWORD_VAULT_ID}/items"
    body = {
        "vault": {"id": ONE_PASSWORD_VAULT_ID},
        "title": f"{user_id}",
        "category": "LOGIN",
        "fields": [
            {"value": email, "purpose": "USERNAME"},
            {
                "purpose": "PASSWORD",
                "generate": True,
                "recipe": {
                    "length": ONE_PASSWORD_GENERATED_PASSWORD_LENGTH,
                    "characterSets": ONE_PASSWORD_GENERATED_PASSWORD_CHARACTER_SETS
                }
            }
        ]
    }

    try:
        response = requests.post(one_password_create_item_url, headers=ONE_PASSWORD_HEADERS, json=body)
        response.raise_for_status()

        if response.status_code != 200:
            print(f"Request failed with status {response.status_code}")
            return None
        
        print(f"New 1Password item for {email} created with title {user_id}!")

    except requests.exceptions.RequestException as e:
        print(f'Error creating new 1Password item: {e}')
        return None



# Updates the Okta password of a user based on their user ID.
def update_okta_password(user_id, email, new_password):
    password_reset_object = {
        "credentials": {
            "password" : { "value": new_password }
        }
    }
    try:
        password_response = requests.post(f'{OKTA_API_ENDPOINT}/api/v1/users/{user_id}', headers=OKTA_HEADERS, data=json.dumps(password_reset_object))
        password_response.raise_for_status()
        if password_response.status_code == 200:
            print(f'Password updated successfully at Okta!')
        else:
            # This part may not be reached due to the raise_for_status() but is good to keep for clarity
            print(f'Unexpected response while resetting password for {email}: {password_response.text} at Okta')
    except requests.exceptions.RequestException as e:
        print(f'Error updating Okta password for {email}: {e}')


# Main function that orchestrates the syncing process between Okta and 1Password.
def main():
    users = get_okta_group_members()
    for user in users:
        email = user['profile']['email']
        user_id = user['id']
        print(f"Processing Okta user with email: {email} and ID: {user_id}")
        
        item_id = fetch_1password_items(user_id)
        if item_id:
            # For existing items: Change the password, wait briefly, and then retrieve the new password.
            change_1password_item_password(item_id)
            time.sleep(3)  # Wait to ensure that 1Password has updated the password.
            new_password = retrieve_1password_item_details(item_id)
            if new_password:
                #print(f"New password (just read from the 1Password vault) for {email}: {new_password}")
                update_okta_password(user_id, email, new_password)
            else:
                print(f"Failed to retrieve the new password for {email} from 1Password after rotation.")
        else:
            # For new items: Create the item, then retrieve the password.
            create_new_1password_item(user_id, email)
            time.sleep(3)  # Wait to ensure that 1Password has created the object.
            item_id = fetch_1password_items(user_id)
            new_password = retrieve_1password_item_details(item_id)
            if new_password:
                #print(f"New password (just read from the 1Password vault) for {email}: {new_password}")
                update_okta_password(user_id, email, new_password)
            else:
                print(f"Failed to retrieve the new password for {email} from 1Password after creation.")
        
        time.sleep(2)


if __name__ == "__main__":
    main()
