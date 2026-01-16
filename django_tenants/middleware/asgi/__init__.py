""" Middleware asynchorous tenants module that handles multiple requests 
    concurrently without blocking other requests. 
"""


class ProtocolTypeRouter:
    """
    Takes a mapping of protocol type names to other Application instances,
    and dispatches to the right one based on protocol name (or raises an error)

    `Adapted from: channels.routing (https://pypi.org/project/channels/)`
    
    PS: If you have channels in your installed app you can simply call it from
    here, it is all your choice.

    #### How to set it up on your `asgi.py` 
        
        ```
        application = ProtocolTypeRouter(
            "http": get_asgi_application()
            ## Other protocols here.
        )

        # in your setting, add this - ASGI_APPLICATION = "your_project.asgi.application"
        ```
   
    You must explicitly mention the key, `http` to route your asgi instances\
      on the ProtocolTypeRouter class.
    """

    def __init__(self, application_mapping):
        self.application_mapping = application_mapping

    async def __call__(self, scope, receive, send):
        if scope["type"] in self.application_mapping:
            application = self.application_mapping[scope["type"]]
            return await application(scope, receive, send)
        else:
            raise ValueError(
                "No application configured for scope type %r" % scope["type"]
            )


class CoreMiddleware:
    """
    Base class for implementing ASGI middleware.

    Note that subclasses of this are not self-safe; don't store state on
    the instance, as it serves multiple application instances. Instead, use
    scope.

    `Adapted from: channels.middleware (https://pypi.org/project/channels/)`


    """

    def __init__(self, inner):
        """
        Middleware constructor that takes inner application.
        """
        self.inner = inner

    async def __call__(self, scope, receive, send):
        """
        ASGI application; can insert things into the scope and run asynchronous
        code.
        """
        # Copy scope to stop changes going upstream
        scope = dict(scope)
        # Run the inner application along with the scope
        return await self.inner(scope, receive, send)

