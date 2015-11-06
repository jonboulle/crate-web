# -*- coding: utf-8; -*-
#
# Licensed to Crate (https://crate.io) under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  Crate licenses
# this file to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  You may
# obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations
# under the License.
#
# However, if you have executed another commercial license agreement
# with Crate these terms will supersede the license and you may use the
# software solely pursuant to the terms of the relevant commercial agreement.

__docformat__ = "reStructuredText"

import os
import re
import json

from pprint import pformat

from datetime import datetime
from markdown2 import markdown

from django.template import Context
from django.template.base import Library
from django.template.loader import get_template
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe

from web.utils import toDict, parseDate, parsePost

POSTS = []
NEWS_JSON = []
DEVELOPER_NEWS_JSON = []


class Collection(object):

    def __init__(self, title, path, pages=[], config={}):
        self.title = title
        self.path = path
        self.pages = self.create_contexts(self._apply_filter(pages))
        self.config = config

    def _apply_filter(self, pages):
        return [p for p in pages \
                if p.path.startswith(self.path) \
                and p.path.endswith('.html')]

    def create_contexts(self, pages):
        contexts = []
        for page in pages:
            # Parse headers and markdown body
            headers, body = parsePost(page)

            # Build a context for each post
            ctx = Context()
            ctx.update(headers)
            ctx['raw_body'] = body
            ctx['path'] = page.path
            ctx['date'] = Collection.to_datetime(headers)
            ctx['url'] = page.absolute_final_url
            ctx['tags'] = Collection.to_list(headers, 'tags')
            ctx['category'] = Collection.to_list(headers, 'category')
            contexts.append(ctx)
        return contexts

    @staticmethod
    def to_list(headers, key):
        if headers.get(key):
            return [h.strip() for h in headers[key].split(',')]
        return []

    @staticmethod
    def to_datetime(headers):
        return parseDate(headers.get('date') or headers.get('created'))

    def filter(self, value, key='tags'):
        return filter(lambda p: value in p.get(key), self.pages)

    def sort(self, key='date', reverse=False):
        self.pages = sorted(self.pages, key=lambda x: x[key])
        if reverse:
            self.pages.reverse()

    def create_navigation(self):
        indexes = range(0, len(self.pages))
        for i in indexes:
            if i+1 in indexes: self.pages[i]['prev_post'] = self.pages[i+1]
            if i-1 in indexes: self.pages[i]['next_post'] = self.pages[i-1]

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def __iter__(self):
        return self.pages.__iter__()

    def __repr__(self):
        return '<{0}: {1}>'.format(self.title, pformat(self.pages))


def preBuild(site):
    settings = site.config.get('settings', {})

    global POSTS
    POSTS = Collection('Blog', 'blog/', pages=site.pages(), config=site.config)
    POSTS.sort('date', reverse=True)
    POSTS.create_navigation()

    global NEWS_JSON
    NEWS_JSON = toDict(settings,
                       POSTS.filter('news', key='category'))

    global DEVELOPER_NEWS_JSON
    DEVELOPER_NEWS_JSON = toDict(settings,
                                 POSTS.filter('developernews', key='category'))


def preBuildPage(site, page, context, data):
    """
    Add the list of posts to every page context so we can
    access them from wherever on the site.
    """
    context['posts'] = POSTS
    context['news_json'] = NEWS_JSON
    context['developer_news_json'] = DEVELOPER_NEWS_JSON

    for post in POSTS:
        if post['path'] == page.path:
            tpl = get_template(post.get('template', 'post.html'))
            raw = force_text(post['raw_body'])
            post['body'] = mark_safe(markdown(raw,
                extras=["fenced-code-blocks","header-ids"]))
            context['__CACTUS_CURRENT_PAGE__'] = page
            context['CURRENT_PAGE'] = page
            context.update(post)
            data = tpl.render(context)

    return context, data

