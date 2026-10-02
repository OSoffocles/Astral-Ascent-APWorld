from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client.launch import launch_client  # imported lazily: only when the client is opened

    launch(launch_client, name="Astral Ascent Client", args=args)


components.append(
    Component(
        "Astral Ascent Client",
        func=run_client,
        game_name="Astral Ascent",
        component_type=Type.CLIENT,
        supports_uri=True,
    )
)
