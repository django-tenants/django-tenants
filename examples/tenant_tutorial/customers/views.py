from django.contrib.auth.models import User
from django.db.utils import DatabaseError
from django.views.generic import FormView
from customers.forms import GenerateUsersForm
from customers.models import Client
from random import choice


class TenantView(FormView):
    form_class = GenerateUsersForm
    template_name = "index_tenant.html"
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenants_list'] = Client.objects.all()
        context['users'] = User.objects.all()
        return context

    def form_valid(self, form):
        User.objects.all().delete()  # clean current users

        # generate five random users
        USERS_TO_GENERATE = 5
        first_names = ["Aiden", "Jackson", "Ethan", "Liam", "Mason", "Noah",
                       "Lucas", "Jacob", "Jayden", "Jack", "Sophia", "Emma",
                       "Olivia", "Isabella", "Ava", "Lily", "Zoe", "Chloe",
                       "Mia", "Madison"]
        last_names = ["Smith", "Brown", "Lee	", "Wilson", "Martin", "Patel",
                      "Taylor", "Wong", "Campbell", "Williams"]

        while User.objects.count() != USERS_TO_GENERATE:
            first_name = choice(first_names)
            last_name = choice(last_names)
            try:
                user = User(username=(first_name+last_name).lower(),
                            email="%s@%s.com" % (first_name, last_name),
                            first_name=first_name,
                            last_name=last_name)
                user.save()
            except DatabaseError:
                pass

        return super().form_valid(form)
