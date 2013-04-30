from copy import deepcopy
import json
import datetime
import time
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.html import strip_tags
import feedparser
from django_odc.objects import ContentItemAuthor, ContentItem


class _BaseChannel(object):

    @property
    def configuration(self):
        return deepcopy(self._configuration)

    def run_test(self, source, configuration, test_result_id):
        # This is designed to be overwritten by subclasses
        pass

    def run_polling_aggregation(self, source, configuration, run_record_id):
        # This is designed to be overwritten by subclasses
        pass


class FeedChannel(_BaseChannel):
    _configuration = {
        'type': 'feed_v01',
        'data_type': 'content_v01',
        'aggregation_type': 'polling',
        'images': {
            '16': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/16/social_rss_box_orange.png',
            '24': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/24/social_rss_box_orange.png',
            '32': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/32/social_rss_box_orange.png',
            '48': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/48/social_rss_box_orange.png',
            '64': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/64/social_rss_box_orange.png',
            '128': 'http://cdn1.iconfinder.com/data/icons/yooicons_set01_socialbookmarks/128/social_rss_box_orange.png'
        },
        'display_name_short': 'Feeds',
        'display_name_full': 'Web Feeds (RSS/ATOM)',
        'description_short': 'Collect content from blogs and news sites.',
        'description_full': 'Use this source to connect to blogs and news sites that publish content via RSS '
                            'or ATOM',
        'config': {
            'elements': [
                {
                    'name': 'feed_url',
                    'display_name': 'The address of the feed',
                    'type': 'text',
                    'help_message': 'This must be the url of the actual feed (the rss or atom items).',
                    'value': ''
                }
            ]
        }
    }

    @classmethod
    def ValidateAndReturnErrors(cls, configuration):
        # Extract the elements from the config
        elements = configuration['config']['elements']
        # Get the feed url for checking
        feed_url = [e for e in elements if e['name'] == 'feed_url'][0]['value']
        # If there is no feed url
        if not feed_url:
            # Return an error saying so
            return ['You must enter an address for this source.']
        try:
            # Use django to validate the url for format
            url_validator = URLValidator()
            url_validator(feed_url)
        except ValidationError, e:
            # Return a error is format does not pass
            return ['The address you entered does not look like a url.']
        try:
            # Use feedparser to check there is a feed at the end of the url
            feed = feedparser.parse(feed_url)
            # If there is no feed then throw an error
            if not feed['feed'] or not feed['entries']:
                raise Exception()
        except Exception, e:
            # return an error saying that a feed does not exist at that url
            return ['The address you provided seems to be for a web page, not a feed (have you tried copying '
                    'it from your browsers address bar?). ']
        # No errors = pass
        return []

    def _parse_feed_item(self, item, source):
        created = None
        try:
            timestamp = time.mktime(item.get('published_parsed'))
            created = datetime.datetime.fromtimestamp(timestamp).strftime('%c')
        except Exception, e:
            pass
        author = ContentItemAuthor()
        author.display_name = item.get('author', '')
        content = ContentItem()
        content.source = source.to_dict()
        content.author = author
        content.title = strip_tags(item.get('title', ''))
        content.link = item.get('link', '')
        content.text = [strip_tags(item.get('description', ''))]
        content.created = created
        return content

    def run_test(self, source, configuration, test_result_id):
        # Validate the config to ensure its ok - it should be but who knows :)
        errors = FeedChannel.ValidateAndReturnErrors(configuration)
        #If these are any errors then set the test in error state
        if errors:
            # Build the status messages
            status_messages = {'errors': ['This source is not correctly configured.'], 'infos': []}
            # Update the test via the source object
            return source.update_test_data(test_result_id, 'error', status_messages)
        # Extract the elements from the config
        elements = configuration['config']['elements']
        # Get the feed url for checking
        feed_url = [e for e in elements if e['name'] == 'feed_url'][0]['value']
        # Begin collecting content from the channel
        try:
            # Create a new feed from the url
            feed = feedparser.parse(feed_url)
        except Exception, e:
            # If there is a feed level error
            return source.update_test_data(
                test_result_id,
                'error',
                {'errors': ['This source is not correctly configured.'], 'infos': []})
        # Check for bozo errors and store them to return them to the UI if they exists
        bozo_errors = []
        if feed.get('bozo'):
            bozo_errors += ['The feed at this address is not well formatted xml.']
            bozo_errors += ['%s' % feed.get('bozo_exception')]
        # Extract the items from the feed
        items = feed.get('items', None)
        # If there are no items
        if not items:
            # Update the source with the error
            return source.update_test_data(
                test_result_id,
                'error',
                {'errors': ['No items could be collected from this address.'] + bozo_errors, 'infos': []})
        # Set up the results variable
        results = []
        # Count the number of content items with no dates
        number_of_items_with_no_date = 0
        # Loop over the items
        for item in feed.get('items'):
            content = self._parse_feed_item(item, source)
            if not content.created:
                number_of_items_with_no_date += 1
            results.append(content)
        # Work out if there are any info messages to show
        info_messages = bozo_errors
        if number_of_items_with_no_date:
            info_messages += ['Some of the items did not have a published date, this can lead to content duplication.']
        # Update the source with the results and include any bozo errors as info messages
        return source.update_test_data(
            test_result_id,
            'passed',
            {'errors': [], 'infos': info_messages},
            results)
    
    def run_polling_aggregation(self, source, configuration, run_record):
        # Validate the config to ensure its ok - it should be but who knows :)
        errors = FeedChannel.ValidateAndReturnErrors(configuration)
        #If these are any errors then set the test in error state
        if errors:
            # Build the status messages
            status_messages = {'errors': ['This source is not correctly configured.'], 'infos': []}
            # Update the run record
            run_record.update('error', status_messages)
            return None
        # Extract the elements from the config
        elements = configuration['config']['elements']
        # Get the feed url for checking
        feed_url = [e for e in elements if e['name'] == 'feed_url'][0]['value']
        # Begin collecting content from the channel
        try:
            # Create a new feed from the url
            feed = feedparser.parse(feed_url)
        except Exception, e:
            # If there is a feed level error update the run record and quit
            run_record.update('error', {'errors': ['This source is not correctly configured.'], 'infos': []})
            return None
        # Check for bozo errors and store them to return them to the UI if they exists
        bozo_errors = []
        if feed.get('bozo'):
            bozo_errors += ['The feed at this address is not well formatted xml.']
            bozo_errors += ['%s' % feed.get('bozo_exception')]
        # Extract the items from the feed
        items = feed.get('items', None)
        # If there are no items
        if not items:
            # update the run and quit
            run_record.update(
                'error',
                {'errors': ['No items could be collected from this address.'] + bozo_errors, 'infos': []})
            return None
        # Set up the results variable
        results = []
        # Loop over the items
        for item in feed.get('items'):
            content = self._parse_feed_item(item, source)
            results.append(content)
        # Work out if there are any info messages to show
        info_messages = bozo_errors
        # calculate oldest and youngest
        oldest = None
        youngest = None
        for r in results:
            if r.created:
                created = datetime.datetime.strptime(r.created, '%c')
                if not oldest or created < oldest:
                    oldest = created
                if not youngest or created > youngest:
                    youngest = created
        # Update the stats on the run record
        run_record.record_statistics(total_item=len(results), oldest_datetime=oldest, youngest_datetime=youngest)
        # update the run record
        run_record.update('finished', {'errors': [], 'infos': info_messages})
        # Return the results
        return results