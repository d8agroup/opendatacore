import datetime
import uuid
from django.utils.timezone import now


class ContentItemAuthor(object):
    display_name = ''


class ContentItem(object):
    id = '%s' % uuid.uuid4()
    source = {}
    author = ContentItemAuthor()
    title = ''
    text = []
    link = ''
    created = now()
