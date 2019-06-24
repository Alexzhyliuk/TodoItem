from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from tasks.forms import AddTaskForm, TodoItemExportForm, TodoItemForm
from tasks.models import TodoItem
from accounts.models import Profile
from trello import TrelloClient
from taggit.managers import TaggableManager
from taggit.models import Tag


@login_required
def index(request):
    return HttpResponse("Примитивный ответ из приложения tasks")


def complete_task(request, uid):
    t = TodoItem.objects.get(id=uid)
    t.is_completed = True
    t.save()
    return HttpResponse("OK")


def add_task(request):
    if request.method == "POST":
        desc = request.POST["description"]
        t = TodoItem(description=desc)
        t.save()
    return redirect(reverse("tasks:list"))


def delete_task(request, uid, tag_slug=None):
    t = TodoItem.objects.get(id=uid)
    t.delete()
    if tag_slug:
        return redirect(reverse("tasks:list_by_tag", args=[ tag_slug ]))
    else:
        return redirect(reverse("tasks:list"))


#class TaskListView(LoginRequiredMixin, ListView):
#    model = TodoItem
#    context_object_name = "tasks"
#    template_name = "tasks/list.html"


#    def get_queryset(self):
#        u = self.request.user
#        qs = super().get_queryset()
#        return qs.filter(owner=u)

#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)

#        user_tasks = self.get_queryset()
#        tags = []
#        for t in user_tasks:
#            tags.append(list(t.tags.all()))
        

#        def filter_tags(tags_by_task):
#            list_of_tags = []
#            for e in tags_by_task:
#                for e2 in e:
#                    if not(e2 in list_of_tags):
#                        list_of_tags.append(e2)
#            return list_of_tags

#        context['tags'] = filter_tags(tags)
#        return context

def tasks_by_tag(request, tag_slug=None):
    u = request.user

    inf = Profile.objects.get(user=u)
    if inf.api_key and inf.api_secret:
        key = inf.api_key
        secret = inf.api_secret
        try:
            client = TrelloClient(api_key=key, api_secret=secret)
        except:
            messages.info(request, "Неправильные данные trello")
        trello_board = client.list_boards()[0]
        trello_list = trello_board.list_lists()[-1]
        tasks_from_trello = trello_list.list_cards()

    def filter_tags(tags_by_task):
            list_of_tags = []
            for e in tags_by_task:
                for e2 in e:
                    list_of_tags.append(e2)
            uniq_list_of_tags = set(list_of_tags)
            return uniq_list_of_tags

    tasks = TodoItem.objects.filter(owner=u).all()

    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        tasks = tasks.filter(tags__in=[tag])

    tags_of_task = []
    for task in tasks:
        taska = task.description
        taga = task.tags.all()
        both = (taska, taga)
        tags_of_task.append(both)
        


    all_tags = []
    for t in tasks:
        all_tags.append(list(t.tags.all()))
    all_tags = filter_tags(all_tags)

    hmt = tasks.count()
    hmt_cmpl = tasks.filter(is_completed=True).count()


    def tags(task):
        intersect = list(filter(lambda x: x in task.tags.all(), all_tags))
        return intersect

#    tags_of_tasks = {}
#   for t in tasks:
#        for tt in list(t.tags.all()):
#            if t.description in tags_of_tasks:
#                tags_of_task[t.description] += tt
#            else:
#                tags_of_task[t.description] = list(tt)


    return render(
        request,
        "tasks/list_by_tag.html",
        {
        "tag": tag,
        "tasks": tasks,
        "all_tags": all_tags,
        "how_much": hmt,
        "hmt_cmpl": hmt_cmpl,
        "tags": tags,
        "trello": tasks_from_trello,
        "tags_and_task": tags_of_task,
        },
    )

class TaskCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = TodoItemForm(request.POST)
        if form.is_valid():
            new_task = form.save(commit=False)
            new_task.owner = request.user
            new_task.save()
            form.save_m2m()
            return redirect(reverse("tasks:list"))

        return render(request, "tasks/create.html", {"form": form})

    def get(self, request, *args, **kwargs):
        form = TodoItemForm()
        return render(request, "tasks/create.html", {"form": form})


class TaskEditView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        t = TodoItem.objects.get(id=pk)
        form = TodoItemForm(request.POST, instance=t)
        if form.is_valid():
            new_task = form.save(commit=False)
            new_task.owner = request.user
            new_task.save()
            return redirect(reverse("tasks:list"))

        return render(request, "tasks/edit.html", {"form": form})

    def get(self, request, pk, *args, **kwargs):
        t = TodoItem.objects.get(id=pk)
        form = TodoItemForm(instance=t)
        return render(request, "tasks/edit.html", {"form": form, "task": t})


class TaskDetailsView(LoginRequiredMixin, DetailView):
    model = TodoItem
    template_name = "tasks/details.html"


class TaskExportView(LoginRequiredMixin, View):
    def generate_body(self, user, priorities, tag_slug):
        q = Q()
        if priorities["prio_high"]:
            q = q | Q(priority=TodoItem.PRIORITY_HIGH)
        if priorities["prio_med"]:
            q = q | Q(priority=TodoItem.PRIORITY_MEDIUM)
        if priorities["prio_low"]:
            q = q | Q(priority=TodoItem.PRIORITY_LOW)
        tasks = TodoItem.objects.filter(owner=user).filter(q).all()
        tasks2 = []
        if tag_slug:
            for task in tasks:
                slugs = []
                for t in task.tags.all():
                    slugs.append(t.slug)

                if tag_slug in slugs:
                    tasks2.append(task)
                    tasks = tasks2
            

        body = "Ваши задачи и приоритеты:\n"
        for t in list(tasks):
            if t.is_completed:
                body += f"[x] {t.description} ({t.get_priority_display()}, тег - {tag_slug})\n"
            else:
                body += f"[ ] {t.description} ({t.get_priority_display()}, тег - {tag_slug})\n"

        return body

    def post(self, request, tag_slug=None, *args, **kwargs):
        form = TodoItemExportForm(request.POST)
        if form.is_valid():
            email = request.user.email
            body = self.generate_body(request.user, form.cleaned_data, tag_slug)
            send_mail("Задачи", body, settings.EMAIL_HOST_USER, [email])
            messages.success(request, "Задачи были отправлены на почту %s" % email)
        else:
            messages.error(request, "Что-то пошло не так, попробуйте ещё раз")
        return redirect(reverse("tasks:list"))

    def get(self, request, tag_slug=None, *args, **kwargs):
        form = TodoItemExportForm()
        return render(request, "tasks/export.html", {"form": form, "tag": tag_slug})
