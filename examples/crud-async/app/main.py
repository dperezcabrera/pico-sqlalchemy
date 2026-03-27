import asyncio

from pico_boot import init
from pico_ioc import configuration, YamlTreeSource

from .services import UserService


async def main():
    config = configuration(YamlTreeSource("config.yml"))

    # pico-boot scans "app" recursively and auto-discovers pico-sqlalchemy
    container = init(modules=["app"], config=config)

    service = await container.aget(UserService)

    # Create users
    alice = await service.create_user("Alice", "alice@example.com")
    bob = await service.create_user("Bob", "bob@example.com")
    print(f"Created: {alice.name} ({alice.email})")
    print(f"Created: {bob.name} ({bob.email})")

    # List all users
    users = await service.list_users()
    print(f"\nAll users ({len(users)}):")
    for u in users:
        print(f"  - {u.name}: {u.email}")

    # Update email
    alice = await service.update_user_email(alice.id, "alice.new@example.com")
    print(f"\nUpdated Alice's email: {alice.email}")

    # Delete Bob
    deleted = await service.delete_user(bob.id)
    print(f"\nDeleted Bob: {deleted}")

    # Final state
    users = await service.list_users()
    print(f"\nFinal users ({len(users)}):")
    for u in users:
        print(f"  - {u.name}: {u.email}")

    await container.ashutdown()


if __name__ == "__main__":
    asyncio.run(main())
