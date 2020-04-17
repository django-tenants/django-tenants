def get_installed_apps(shared_app, tenant_app):
    return list(shared_app) + [app for app in tenant_app if app not in shared_app]
