from django.template import Library
from django.template.defaulttags import URLNode
from django.template.defaulttags import url as default_url
from django_tenants.utils import clean_tenant_url, get_public_schema_name

register = Library()


class SchemaURLNode(URLNode):
    def __init__(self, url_node):
        super(SchemaURLNode, self).__init__(url_node.view_name, url_node.args, url_node.kwargs, url_node.asvar)

    def render(self, context):
        url = super(SchemaURLNode, self).render(context)
        return clean_tenant_url(url)


@register.tag
def url(parser, token):
    return SchemaURLNode(default_url(parser, token))


@register.simple_tag
def public_schema():
    return get_public_schema_name()
