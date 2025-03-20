import string
from cincoconfig import generate_argparse_parser
from xkcdpass.xkcd_password import generate_wordlist

from one_request import setup
from one_request.config import config
from one_request.db.models import *
from one_request.ctf.data import *

import random

WORDLIST = generate_wordlist()
# global session
session: Session = None


def insert_chat_messages(group: Group, messages: tuple[str, str]):
    # Create chat
    chat = Chat(
        name="Council Discussion",
        description="Private council communications",
        group_id=group.id,
    ).upsert(Chat.name, session=session)

    users = {}  # cache users

    # unpack tuple of name, message
    for i, (username, message) in enumerate(messages):
        if name not in users:
            users[name] = User.one(User.name == name)
            UserChatLink(user_id=users[name].id, chat_id=chat.id).upsert(
                UserChatLink.user_id, UserChatLink.chat_id, session=session
            )
        ChatMessage(
            chat_id=chat.id,
            user_id=users[name].id,
            message=message,
        ).upsert(ChatMessage.chat_id, ChatMessage.user_id, ChatMessage.message, session=session)

    return chat


def generate_intern_request(staff: User, intern_user: User) -> None:
    """Generate the specific intern support request for finding palantir endpoint"""
    # Create support request from intern
    intern_request = SupportRequest(
        user_id=intern_user.id, resolved=True, title="[ADMIN] Urgent: Orc Raid Relocation Request"
    ).save(session=session)

    # Initial message from intern
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=intern_user.id,
        message="Orc raid reported near Weathertop. Need to relocate a group's archery training to Rivendell, but getting 'Access Denied' when trying to use /groups/:group_id/activities/:activity_id/schedule/:location_id endpoint. Any guidance?",
    ).save(session=session)

    # Staff response with palantir hint
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=staff.id,
        message="Ah, for emergency relocations, staff can generate short-lived tokens using /palantir/glimpse - think of it as borrowing the sight of the seeing-stones, though the vision fades quickly for safety.",
    ).save(session=session)

    # Intern followup
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=intern_user.id,
        message="Got the token, but I also need their private event invite code. We just implemented that hashing feature - any way to decode it? Need to ensure only the original participants can join.",
    ).save(session=session)

    # Staff provides guidance
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=staff.id,
        message="The hashing is like elvish encryption - meant to be one-way! But since it's a group event, try viewing their communications via /palantir/groups/:id/chats. If you can't find it there, locate their user_id and send a direct message. You'll need that user_id anyway to maintain proper ownership of the relocated event.",
    ).save(session=session)

    # Intern expresses concern
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=intern_user.id,
        message="Found the invite code in their group chat! Though it feels a bit like using the palantir for... questionable purposes. Should we have this level of access?",
    ).save(session=session)

    # Staff justifies
    SupportRequestMessage(
        request_id=intern_request.id,
        user_id=staff.id,
        message="The power to see all is a heavy responsibility, like the seeing-stones themselves. We use it only for maintaining order in these realms - though you're wise to question it. Just ensure you document all access in the records of Minas Tirith.",
    ).save(session=session)


def generate_support_requests(users: list[User], groups: list[Group]) -> List[SupportRequest]:
    """Generate support requests and messages from 2 years ago"""
    # Create users if they don't exist
    intern_user = User(
        name="Guard Trainee",
        email="intern@minas-tirith.gov",
        password="trainee_password",
        role=UserRole.USER,
        primary_group_name="guards_in_training",
    ).upsert(User.email, session=session)

    chief = User(
        name="Chief Guard",
        email="guard-captain@minas-tirith.gov",
        password="captain_password",
        role=UserRole.STAFF,
        primary_group_name="guard_captains",
    ).upsert(User.email, session=session)

    users = User.all(User.role == UserRole.USER)
    staff_users = [
        chief,
        *User.all(User.role == UserRole.STAFF),
    ]

    def gen_request(user: User, staff: User) -> SupportRequest:
        """Generate a single support request with coherent conversation flow"""
        # Select random group
        group = random.choice(groups) if random.random() > 0.5 else None

        # Select random flow
        flow = SUPPORT_FLOWS.pop()

        # Create support request
        request = SupportRequest(
            user_id=user.id, group_id=group.id if group else None, resolved=random.random() > 0.1, title=flow["title"]
        ).save(session=session)

        # Initial message
        SupportRequestMessage(request_id=request.id, user_id=user.id, message=flow["initial"]).save(session=session)

        # add message responses
        for i in range(3):
            # User response
            if i < len(flow["user_responses"]):
                SupportRequestMessage(request_id=request.id, user_id=user.id, message=flow["user_responses"][i]).save(
                    session=session
                )

            # Staff response
            if i < len(flow["staff_responses"]):
                SupportRequestMessage(request_id=request.id, user_id=staff.id, message=flow["staff_responses"][i]).save(
                    session=session
                )

        return request

    requests = []
    # Create regular support requests with the special request in the middle
    for _ in range(random.randint(7, 10)):
        requests.append(gen_request(random.choice(users), random.choice(staff_users)))

    requests.append(generate_intern_request(chief, intern_user))

    try:
        for i in range(random.randint(7, 10)):
            requests.append(gen_request(random.choice(users), random.choice(staff_users)))
    except IndexError:
        print("ran out of flows to use")

    return requests


def categorize_by_keywords(name: str, description: str) -> str:
    """Determine category based on name and description keywords"""
    keywords = {
        "forest": ["forest", "wood", "tree", "grove"],
        "mountain": ["mountain", "peak", "cave", "mine"],
        "city": ["city", "town", "settlement", "fortress"],
        "valley": ["valley", "dale", "glen", "vale"],
        "inn": ["inn", "tavern", "house", "lodge"],
        "adventure": ["quest", "journey", "expedition", "adventure"],
        "relaxation": ["rest", "peace", "healing", "sanctuary"],
        "training": ["training", "practice", "learning", "study"],
        "feast": ["feast", "celebration", "gathering", "festival"],
        "exploration": ["explore", "discover", "seek", "find"],
    }

    text = (name + " " + description).lower()
    for category, words in keywords.items():
        if any(word in text for word in words):
            return category
    return random.choice(list(keywords.keys()))


def generate_bulk_reviews(target_user_id: UUID, count: int = 100) -> List[Review]:
    users = User.all(User.id != target_user_id)
    locations = Location.all()
    activities = Activity.all()

    reviews = []

    for _ in range(count):
        user = random.choice(users)
        is_location = random.choice([True, False])

        parts = [
            f"{random.choice(OPENINGS)} {random.choice(QUALITIES)}.",
            random.choice(DESCRIPTORS) + ".",
        ]

        if is_location:
            parts.append(random.choice(CONCLUSIONS) + ".")
        else:
            parts.append(random.choice(ACTIVITY_PRAISE) + ".")

        review = Review(user_id=user.id, name=user.name, rating=random.randint(2, 4), review=" ".join(parts))

        if is_location:
            review.location_id = random.choice(locations).id
        else:
            review.activity_id = random.choice(activities).id

        reviews.append(review)

    session.add_all(reviews)
    session.commit()

    return reviews


def generate_target_reviews(target_user: User, target_group: Group):
    locations = {loc.name: loc for loc in Location.all(Location.name.in_(preferred_locations))}

    # Create reviews
    for review_data in location_reviews:
        Review(
            user_id=target_user.id,
            name=target_user.name,
            location_id=locations[review_data["location"]].id,
            rating=review_data["rating"],
            review=review_data["review"],
        ).save(session=session)


def generate_users() -> tuple[User, Group, list[User], list[Group]]:
    """Create users and groups with proper relationships"""
    # Create users first without group associations
    users = {}
    target_user = None
    target_group = None
    for user_data in USERS:
        if existing := User.first(or_(User.email == user_data["email"], User.name == user_data["name"])):
            user = existing
        else:
            user = User(
                name=user_data["name"],
                email=user_data["email"],
                password=user_data["password"],
                role=user_data.get("role", UserRole.USER),
                primary_group_name=user_data["primary_group"],
            ).save(session=session)

        users[user_data["email"]] = user
        if user.email == TARGET_USER.get("email"):
            target_user = user

    # Create groups with owners
    groups = {}
    for group_data in GROUPS:
        # Find an appropriate owner based on group membership
        owner = None
        if group_data.get("owner"):
            owner = users[group_data["owner"]]

        if not owner:
            for user_data in USERS:
                if group_data["name"] in user_data["groups"] and users.get(user_data["email"]):
                    owner = users[user_data["email"]]
                    break
        if not owner:
            # well fuck it, that didn't work
            owner = random.choice(list(users.values()))

        group = groups[group_data["name"]] = Group(
            name=group_data["name"], description=group_data["description"], owner_id=owner.id
        ).upsert(Group.name, session=session)

        if group.name == TARGET_GROUP.get("name"):
            target_group = group

    # Update user group associations
    for user_data in USERS:
        user = users[user_data["email"]]
        for g in user_data["groups"]:
            UserGroupLink(user_id=user.id, group_id=groups[g].id).upsert(
                UserGroupLink.user_id,
                UserGroupLink.group_id,
            )

    # session.add(group_links)
    session.commit()
    # user.groups = [groups[g] for g in user_data["groups"]]
    # user.save(session=session)

    return target_user, target_group, list(users.values()), list(groups.values())


def generate_random_coordinates() -> tuple[str, str]:
    # Generate random coordinates that could plausibly be in a temperate zone
    # todo make this a list of interesting coordinates
    return str(random.uniform(40.0, 60.0)), str(random.uniform(-10.0, 40.0))


def generate_locations() -> list[Location]:
    generated = []

    for name, description, lat, long in LOCATION_TEMPLATES:
        # lat, long = generate_random_coordinates()
        generated.append(
            Location(name=name, description=description, lat=lat, long=long).upsert(Location.name, session=session)
        )

    return generated


def generate_public_activities(users: Sequence[User], before_today=180, after_today=180):
    start = date.today() - timedelta(days=before_today)
    end = date.today() + timedelta(days=after_today)
    total = len(ACTIVITY_TEMPLATES)
    n = 0

    for (
        name,
        description,
        frequency,
        variance,
        price,
        currency,
        locations,
        creator_email,
        _,
    ) in ACTIVITY_TEMPLATES:
        # Generate random price (rounded to nearest 10)
        price = price or round(random.uniform(10, 500) / 10) * 10
        creator = User.one(User.email == creator_email)
        group_id = None
        # if group_name:
        #     group = Group.one(Group.name == group_name)
        #     group_id = group.id

        day = start + timedelta(days=frequency)
        count = 0
        n += 1
        print(f"creating public activities from {start} to {end}")
        while day < end:
            print(f"\rprogress: {n} / {total}: {day} / {end} ({frequency} day(s) at a time)", end="")
            count += 1

            if random.randint(1, 10) < 5:
                # randomly skip some dates to reduce activity count
                continue

            offset = random.randint(-int(frequency * variance), int(frequency * variance))
            day = start + timedelta(days=frequency * count) + timedelta(days=offset)

            if not start < day < end:
                print("\tWARNING: day out of range, skipping", day, start, end)
                continue

            location_name = random.choice(locations)
            location = Location.one(Location.name == location_name)

            # protect target location on target day
            if location == TARGET_LOCATION and day == TARGET_ACTIVITY["day"]:
                day += timedelta(days=1)

            invite_code_hash = None
            if random.randint(1, 10) < 2:
                invite_code = "".join(random.choice(string.ascii_letters) for _ in range(5))
                invite_code_hash = BcryptPasswordHandler.hash(invite_code, rounds=4).hash

            activity = Activity(
                day=day,
                creator_id=creator.id,
                invite_code=invite_code_hash,
                name=name,
                description=description,
                price=price,
                currency=currency,
                location=location,
                group_id=group_id,
            ).upsert(Activity.name, Activity.day, session=session)

            # add users
            ActivityUserLink(activity_id=activity.id, user_id=creator.id).upsert(
                ActivityUserLink.activity_id, ActivityUserLink.user_id, session=session
            )
            for user in random.sample(users, random.randint(1, len(users))):
                ActivityUserLink(activity_id=activity.id, user_id=user.id).upsert(
                    ActivityUserLink.activity_id, ActivityUserLink.user_id, session=session
                )


def generate_private_activities(users: Sequence[User], before_today=360, after_today=360):
    start = date.today() - timedelta(days=before_today)
    end = date.today() + timedelta(days=after_today)
    variance = 0.2
    n = 0
    total = sum(len(items) for items in PRIVATE_EVENTS.values())

    for location_name, activities in PRIVATE_EVENTS.items():
        for template in activities:
            frequency = template["frequency"]
            group = Group.one(Group.name == template["group"])
            location = Location.one(Location.name == location_name)
            # target activity has no frequecy
            day = start + timedelta(days=frequency) if frequency is not None else template["day"]
            n += 1
            count = 0

            while day < end:
                print(f"\rprogress: {n} / {total}: {day} / {end} ({frequency} day(s) at a time)", end="")
                count += 1
                if frequency is None:
                    # handle target activity on specific date
                    day = template["day"]
                else:
                    offset = random.randint(-int(frequency * variance), int(frequency * variance))
                    day = start + timedelta(days=frequency * count) + timedelta(days=offset)

                if not start < day < end:
                    print("\tWARNING: day out of range, skipping", day, start, end)
                    continue

                # protect target location on target day
                if location == TARGET_LOCATION and day == TARGET_ACTIVITY["day"]:
                    day += timedelta(days=1)

                invite_code = template["invite_code"]
                invite_code_hash = BcryptPasswordHandler.hash(invite_code, rounds=4).hash

                activity = Activity(
                    day=day,
                    creator_id=group.owner_id,
                    invite_code=invite_code_hash,
                    name=template["name"],
                    description=template["description"],
                    price=template["price"],
                    currency=template["currency"],
                    location=location,
                    group_id=group.id,
                ).upsert(Activity.name, Activity.day, session=session)

                # assert activity.check_invite_code(TARGET_INVITE_CODE)

                # add users
                ActivityUserLink(activity_id=activity.id, user_id=group.owner_id).upsert(
                    ActivityUserLink.activity_id, ActivityUserLink.user_id, session=session
                )
                for user in random.sample(users, random.randint(1, 10)):
                    ActivityUserLink(activity_id=activity.id, user_id=user.id).upsert(
                        ActivityUserLink.activity_id, ActivityUserLink.user_id, session=session
                    )

                if frequency is None:
                    # handle target activity on specific date
                    break


def ensure_activities_on_target_day():
    day = TARGET_ACTIVITY["day"]
    for location_name, _, lat, long in LOCATION_TEMPLATES:
        if not is_location_viable(lat, long):
            # skip locations outside of target area
            continue

        if location_name == TARGET_LOCATION:
            print("skipping target location")
            continue

        location = Location.one(Location.name == location_name, relations=["activities"])
        # if Activity.first(Booking.location_id == location.id, Activity.day == day):
        activities = Activity.all(Activity.location == location, Activity.day == day)
        if activities:
            # already exists, continue
            print("target day activity already exists for", location_name)
            continue

        # create activity
        choices = list(filter(lambda a: location_name in a[6], ACTIVITY_TEMPLATES)) or ACTIVITY_TEMPLATES
        activity_name, description, _, _, price, currency, _, creator_email, group_name = random.choice(choices)
        creator = User.one(User.email == creator_email)
        group_id = Group.one(Group.name == group_name).id if group_name else None
        print(
            f"creating {day=} {activity_name=} {description=} "
            f"{price=} {currency=} {location_name=} {creator_email=} {group_name=}"
        )

        Activity(
            day=day,
            creator_id=creator.id,
            name=activity_name,
            description=description,
            price=price or round(random.uniform(10, 500) / 10) * 10,
            currency=currency,
            location=location,
            group_id=group_id,
        ).save(session=session)


def generate_calendar(before_today: int, after_today: int):
    start = day = date.today() - timedelta(days=before_today)
    end = date.today() + timedelta(days=after_today)
    print(f"generating calendar days from {start} to {end}")
    while day <= end:
        print("\r", day, end="")
        # generate from one year ago to one year in the future
        Calendar(day=day).upsert(Calendar.day, session=session)
        day += timedelta(days=1)


def main():
    print("generate calendar")
    generate_calendar(before_today=500, after_today=500)

    print("generate users")
    target_user, target_group, users, groups = generate_users()

    # todo update default baseUrl in postman overrides.json
    # this is a test user for development and should not be enabled in prod
    # print("generate test user")
    admin_user_email = "frodo@baggins.community"
    if not (User.first(User.email == admin_user_email)):
        print("get default group")
        default_group = Group.first(Group.name == DEFAULT_GROUP["name"])
        print("create admin user")
        User(
            id=UUID("590490e4-4ec2-4bdc-84ab-1a61cef85ecc"),  # static ID so tokens remain valid
            name="Frodo Baggins",
            email=admin_user_email,
            password=BcryptPasswordHandler.hash("gonna_be_fine").hash,
            primary_group_name="%bag%end%",
            role=UserRole.ADMIN,
            groups=[default_group],
        ).save(session=session)

    if not (locations := Location.all()):
        print("generate locations")
        locations = generate_locations()

    if not Activity.all():
        print("generate public activities (this takes awhile...)")
        generate_public_activities(
            User.all(User.email.in_(u["email"] for u in GENERIC_USERS)),
            before_today=180,
            after_today=180,
        )
        print("\ngenerate private activities (this takes awhile...)")
        generate_private_activities(
            User.all(User.email.in_(u["email"] for u in [*GENERIC_USERS, *PREMADE_USERS])),
            before_today=365,
            after_today=365,
        )

    if not (Review.all()):
        print("generate reviews")
        generate_target_reviews(target_user, target_group)
        generate_bulk_reviews(target_user.id, random.randint(75, 125))

    if not (support_requests := SupportRequest.all()):
        print("generate support requests")
        support_requests = generate_support_requests(users, groups)

    print("insert chat messages")
    insert_chat_messages(target_group, TARGET_CHAT_MESSAGES)

    print("ensure activities on target day")
    ensure_activities_on_target_day()
    print("done!")


if __name__ == "__main__":
    parser = generate_argparse_parser(config)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config.cmdline_args_override(args, ignore=["force"])
    app_settings = setup(args=args, args_ignore=["force"])
    session = Session(expire_on_commit=False)

    main()
