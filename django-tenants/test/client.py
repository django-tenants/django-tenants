from django.test import RequestFactory, Client
from tenant_schemas.middleware import TenantMiddleware


class TenantRequestFactory(RequestFactory):
    tm = TenantMiddleware()

    def __init__(self, tenant, **defaults):
        super(TenantRequestFactory, self).__init__(**defaults)
        self.tenant = tenant

    def get(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantRequestFactory, self).get(path, data, **extra)

    def post(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantRequestFactory, self).post(path, data, **extra)

    def patch(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantRequestFactory, self).patch(path, data, **extra)

    def put(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantRequestFactory, self).put(path, data, **extra)

    def delete(self, path, data='', content_type='application/octet-stream',
               **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantRequestFactory, self).delete(path, data, **extra)


class TenantClient(Client):
    tm = TenantMiddleware()

    def __init__(self, tenant, enforce_csrf_checks=False, **defaults):
        super(TenantClient, self).__init__(enforce_csrf_checks, **defaults)
        self.tenant = tenant

    def get(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantClient, self).get(path, data, **extra)

    def post(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantClient, self).post(path, data, **extra)

    def patch(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantClient, self).patch(path, data, **extra)

    def put(self, path, data={}, **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantClient, self).put(path, data, **extra)

    def delete(self, path, data='', content_type='application/octet-stream',
               **extra):
        if 'HTTP_HOST' not in extra:
            extra['HTTP_HOST'] = self.tenant.domain_url

        return super(TenantClient, self).delete(path, data, **extra)
