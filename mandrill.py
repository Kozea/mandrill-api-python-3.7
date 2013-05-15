import requests, os.path, logging, sys, time
try:
    import ujson as json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        import json

class Error(Exception):
    pass
class ValidationError(Error):
    pass
class InvalidKeyError(Error):
    pass
class UnknownTemplateError(Error):
    pass
class InvalidTagNameError(Error):
    pass
class InvalidRejectError(Error):
    pass
class UnknownSenderError(Error):
    pass
class UnknownUrlError(Error):
    pass
class InvalidTemplateError(Error):
    pass
class UnknownWebhookError(Error):
    pass
class UnknownInboundDomainError(Error):
    pass
class UnknownExportError(Error):
    pass

ROOT = 'https://mandrillapp.com/api/1.0/'
ERROR_MAP = {
    'ValidationError': ValidationError,
    'Invalid_Key': InvalidKeyError,
    'Unknown_Template': UnknownTemplateError,
    'Invalid_Tag_Name': InvalidTagNameError,
    'Invalid_Reject': InvalidRejectError,
    'Unknown_Sender': UnknownSenderError,
    'Unknown_Url': UnknownUrlError,
    'Invalid_Template': InvalidTemplateError,
    'Unknown_Webhook': UnknownWebhookError,
    'Unknown_InboundDomain': UnknownInboundDomainError,
    'Unknown_Export': UnknownExportError
}

logger = logging.getLogger('mandrill')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stderr))

class Mandrill(object):
    def __init__(self, apikey=None, debug=False):
        '''Initialize the API client

        Args:
           apikey (str|None): provide your Mandrill API key.  If this is left as None, we will attempt to get the API key from the following locations::
               - MANDRILL_APIKEY in the environment vars
               - ~/.mandrill.key for the user executing the script
               - /etc/mandrill.key
           debug (bool): set to True to log all the request and response information to the "mandrill" logger at the INFO level.  When set to false, it will log at the DEBUG level.  By default it will write log entries to STDERR
       '''

        self.session = requests.session()
        if debug:
            self.level = logging.INFO
        else:
            self.level = logging.DEBUG
        self.last_request = None

        if apikey is None:
            if 'MANDRILL_APIKEY' in os.environ:
                apikey = os.environ['MANDRILL_APIKEY']
            else:
                apikey = self.read_configs()

        if apikey is None: raise Error('You must provide a Mandrill API key')
        self.apikey = apikey

        self.templates = Templates(self)
        self.exports = Exports(self)
        self.users = Users(self)
        self.rejects = Rejects(self)
        self.inbound = Inbound(self)
        self.tags = Tags(self)
        self.messages = Messages(self)
        self.whitelists = Whitelists(self)
        self.internal = Internal(self)
        self.urls = Urls(self)
        self.webhooks = Webhooks(self)
        self.senders = Senders(self)

    def call(self, url, params=None):
        '''Actually make the API call with the given params - this should only be called by the namespace methods - use the helpers in regular usage like m.tags.list()'''
        if params is None: params = {}
        params['key'] = self.apikey
        params = json.dumps(params)
        self.log('POST to %s%s.json: %s' % (ROOT, url, params))
        start = time.time()
        r = self.session.post('%s%s.json' % (ROOT, url), data=params, headers={'content-type': 'application/json', 'user-agent': 'Mandrill-Python/1.0.34'})
        try:
            remote_addr = r.raw._original_response.fp._sock.getpeername() # grab the remote_addr before grabbing the text since the socket will go away
        except:
            remote_addr = (None, None) #we use two private fields when getting the remote_addr, so be a little robust against errors

        response_body = r.text
        complete_time = time.time() - start
        self.log('Received %s in %.2fms: %s' % (r.status_code, complete_time * 1000, r.text))
        self.last_request = {'url': url, 'request_body': params, 'response_body': r.text, 'remote_addr': remote_addr, 'response': r, 'time': complete_time}

        result = json.loads(response_body)

        if r.status_code != requests.codes.ok:
            raise self.cast_error(result)
        return result

    def cast_error(self, result):
        '''Take a result representing an error and cast it to a specific exception if possible (use a generic mandrill.Error exception for unknown cases)'''
        if not 'status' in result or result['status'] != 'error' or not 'name' in result:
            raise Error('We received an unexpected error: %r' % result)

        if result['name'] in ERROR_MAP:
            return ERROR_MAP[result['name']](result['message'])
        return Error(result['message'])

    def read_configs(self):
        '''Try to read the API key from a series of files if it's not provided in code'''
        paths = [os.path.expanduser('~/.mandrill.key'), '/etc/mandrill.key']
        for path in paths:
            try:
                f = open(path, 'r')
                apikey = f.read().strip()
                f.close()
                if apikey != '':
                    return apikey
            except:
                pass

        return None

    def log(self, *args, **kwargs):
        '''Proxy access to the mandrill logger, changing the level based on the debug setting'''
        logger.log(self.level, *args, **kwargs)

    def __repr__(self):
        return '<Mandrill %s>' % self.apikey

class Templates(object):
    def __init__(self, master):
        self.master = master

    def add(self, name, from_email=None, from_name=None, subject=None, code=None, text=None, publish=True):
        """Add a new template

        Args:
           name (string): the name for the new template - must be unique
           from_email (string): a default sending address for emails sent using this template
           from_name (string): a default from name to be used
           subject (string): a default subject line to be used
           code (string): the HTML code for the template with mc:edit attributes for the editable elements
           text (string): a default text part to be used when sending with this template
           publish (boolean): set to false to add a draft template without publishing

        Returns:
           struct.  the information saved about the new template::
               slug (string): the immutable unique code name of the template
               name (string): the name of the template
               code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
               subject (string): the subject line of the template, if provided - draft version
               from_email (string): the default sender address for the template, if provided - draft version
               from_name (string): the default sender from name for the template, if provided - draft version
               text (string): the default text part of messages sent with the template, if provided - draft version
               publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
               publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
               publish_subject (string): the subject line of the template, if provided
               publish_from_email (string): the default sender address for the template, if provided
               publish_from_name (string): the default sender from name for the template, if provided
               publish_text (string): the default text part of messages sent with the template, if provided
               published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
               created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
               updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format

        Raises:
           InvalidTemplateError: The given template name already exists or contains invalid characters
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name, 'from_email': from_email, 'from_name': from_name, 'subject': subject, 'code': code, 'text': text, 'publish': publish}
        return self.master.call('templates/add', _params)

    def info(self, name):
        """Get the information for an existing template

        Args:
           name (string): the immutable name of an existing template

        Returns:
           struct.  the requested template information::
               slug (string): the immutable unique code name of the template
               name (string): the name of the template
               code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
               subject (string): the subject line of the template, if provided - draft version
               from_email (string): the default sender address for the template, if provided - draft version
               from_name (string): the default sender from name for the template, if provided - draft version
               text (string): the default text part of messages sent with the template, if provided - draft version
               publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
               publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
               publish_subject (string): the subject line of the template, if provided
               publish_from_email (string): the default sender address for the template, if provided
               publish_from_name (string): the default sender from name for the template, if provided
               publish_text (string): the default text part of messages sent with the template, if provided
               published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
               created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
               updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format

        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name}
        return self.master.call('templates/info', _params)

    def update(self, name, from_email=None, from_name=None, subject=None, code=None, text=None, publish=True):
        """Update the code for an existing template. If null is provided for any fields, the values will remain unchanged.

        Args:
           name (string): the immutable name of an existing template
           from_email (string): the new default sending address
           from_name (string): the new default from name
           subject (string): the new default subject line
           code (string): the new code for the template
           text (string): the new default text part to be used
           publish (boolean): set to false to update the draft version of the template without publishing

        Returns:
           struct.  the template that was updated::
               slug (string): the immutable unique code name of the template
               name (string): the name of the template
               code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
               subject (string): the subject line of the template, if provided - draft version
               from_email (string): the default sender address for the template, if provided - draft version
               from_name (string): the default sender from name for the template, if provided - draft version
               text (string): the default text part of messages sent with the template, if provided - draft version
               publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
               publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
               publish_subject (string): the subject line of the template, if provided
               publish_from_email (string): the default sender address for the template, if provided
               publish_from_name (string): the default sender from name for the template, if provided
               publish_text (string): the default text part of messages sent with the template, if provided
               published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
               created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
               updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format

        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name, 'from_email': from_email, 'from_name': from_name, 'subject': subject, 'code': code, 'text': text, 'publish': publish}
        return self.master.call('templates/update', _params)

    def publish(self, name):
        """Publish the content for the template. Any new messages sent using this template will start using the content that was previously in draft.

        Args:
           name (string): the immutable name of an existing template

        Returns:
           struct.  the template that was published::
               slug (string): the immutable unique code name of the template
               name (string): the name of the template
               code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
               subject (string): the subject line of the template, if provided - draft version
               from_email (string): the default sender address for the template, if provided - draft version
               from_name (string): the default sender from name for the template, if provided - draft version
               text (string): the default text part of messages sent with the template, if provided - draft version
               publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
               publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
               publish_subject (string): the subject line of the template, if provided
               publish_from_email (string): the default sender address for the template, if provided
               publish_from_name (string): the default sender from name for the template, if provided
               publish_text (string): the default text part of messages sent with the template, if provided
               published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
               created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
               updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format

        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name}
        return self.master.call('templates/publish', _params)

    def delete(self, name):
        """Delete a template

        Args:
           name (string): the immutable name of an existing template

        Returns:
           struct.  the template that was deleted::
               slug (string): the immutable unique code name of the template
               name (string): the name of the template
               code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
               subject (string): the subject line of the template, if provided - draft version
               from_email (string): the default sender address for the template, if provided - draft version
               from_name (string): the default sender from name for the template, if provided - draft version
               text (string): the default text part of messages sent with the template, if provided - draft version
               publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
               publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
               publish_subject (string): the subject line of the template, if provided
               publish_from_email (string): the default sender address for the template, if provided
               publish_from_name (string): the default sender from name for the template, if provided
               publish_text (string): the default text part of messages sent with the template, if provided
               published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
               created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
               updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format

        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name}
        return self.master.call('templates/delete', _params)

    def list(self, ):
        """Return a list of all the templates available to this user

        Returns:
           array.  an array of structs with information about each template::
               [] (struct): the information on each template in the account::
                   [].slug (string): the immutable unique code name of the template
                   [].name (string): the name of the template
                   [].code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements - draft version
                   [].subject (string): the subject line of the template, if provided - draft version
                   [].from_email (string): the default sender address for the template, if provided - draft version
                   [].from_name (string): the default sender from name for the template, if provided - draft version
                   [].text (string): the default text part of messages sent with the template, if provided - draft version
                   [].publish_name (string): the same as the template name - kept as a separate field for backwards compatibility
                   [].publish_code (string): the full HTML code of the template, with mc:edit attributes marking the editable elements that are available as published, if it has been published
                   [].publish_subject (string): the subject line of the template, if provided
                   [].publish_from_email (string): the default sender address for the template, if provided
                   [].publish_from_name (string): the default sender from name for the template, if provided
                   [].publish_text (string): the default text part of messages sent with the template, if provided
                   [].published_at (string): the date and time the template was last published as a UTC string in YYYY-MM-DD HH:MM:SS format, or null if it has not been published
                   [].created_at (string): the date and time the template was first created as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].updated_at (string): the date and time the template was last modified as a UTC string in YYYY-MM-DD HH:MM:SS format


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('templates/list', _params)

    def time_series(self, name):
        """Return the recent history (hourly stats for the last 30 days) for a template

        Args:
           name (string): the name of an existing template

        Returns:
           array.  the array of history information::
               [] (struct): the stats for a single hour::
                   [].time (string): the hour as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the number of emails that were sent during the hour
                   [].hard_bounces (integer): the number of emails that hard bounced during the hour
                   [].soft_bounces (integer): the number of emails that soft bounced during the hour
                   [].rejects (integer): the number of emails that were rejected during the hour
                   [].complaints (integer): the number of spam complaints received during the hour
                   [].opens (integer): the number of emails opened during the hour
                   [].unique_opens (integer): the number of unique opens generated by messages sent during the hour
                   [].clicks (integer): the number of tracked URLs clicked during the hour
                   [].unique_clicks (integer): the number of unique clicks generated by messages sent during the hour


        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'name': name}
        return self.master.call('templates/time-series', _params)

    def render(self, template_name, template_content, merge_vars=None):
        """Inject content and optionally merge fields into a template, returning the HTML that results

        Args:
           template_name (string): the immutable name of a template that exists in the user's account
           template_content (array): an array of template content to render.  Each item in the array should be a struct with two keys - name: the name of the content block to set the content for, and content: the actual content to put into the block::
               template_content[] (struct): the injection of a single piece of content into a single editable region::
                   template_content[].name (string): the name of the mc:edit editable region to inject into
                   template_content[].content (string): the content to inject

           merge_vars (array): optional merge variables to use for injecting merge field content.  If this is not provided, no merge fields will be replaced.::
               merge_vars[] (struct): a single merge variable::
                   merge_vars[].name (string): the merge variable's name. Merge variable names are case-insensitive and may not start with _
                   merge_vars[].content (string): the merge variable's content


        Returns:
           struct.  the result of rendering the given template with the content and merge field values injected::
               html (string): the rendered HTML as a string

        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'template_name': template_name, 'template_content': template_content, 'merge_vars': merge_vars}
        return self.master.call('templates/render', _params)


class Exports(object):
    def __init__(self, master):
        self.master = master

    def info(self, id):
        """Returns information about an export job. If the export job's state is 'complete',
the returned data will include a URL you can use to fetch the results. Every export
job produces a zip archive, but the format of the archive is distinct for each job
type. The api calls that initiate exports include more details about the output format
for that job type.

        Args:
           id (string): an export job identifier

        Returns:
           struct.  the information about the export::
               id (string): the unique identifier for this Export. Use this identifier when checking the export job's status
               created_at (string): the date and time that the export job was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               type (string): the type of the export job - activity, reject, or whitelist
               finished_at (string): the date and time that the export job was finished as a UTC string in YYYY-MM-DD HH:MM:SS format
               state (string): the export job's state - waiting, working, complete, error, or expired.
               result_url (string): the url for the export job's results, if the job is completed.

        Raises:
           UnknownExportError: The requested export job does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'id': id}
        return self.master.call('exports/info', _params)

    def list(self, ):
        """Returns a list of your exports.

        Returns:
           array.  the account's exports::
               [] (struct): the individual export info::
                   [].id (string): the unique identifier for this Export. Use this identifier when checking the export job's status
                   [].created_at (string): the date and time that the export job was created as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].type (string): the type of the export job - activity, reject, or whitelist
                   [].finished_at (string): the date and time that the export job was finished as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].state (string): the export job's state - waiting, working, complete, error, or expired.
                   [].result_url (string): the url for the export job's results, if the job is completed.


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('exports/list', _params)

    def rejects(self, notify_email=None):
        """Begins an export of your rejection blacklist. The blacklist will be exported to a zip archive
containing a single file named rejects.csv that includes the following fields: email,
reason, detail, created_at, expires_at, last_event_at, expires_at.

        Args:
           notify_email (string): an optional email address to notify when the export job has finished.

        Returns:
           struct.  information about the rejects export job that was started::
               id (string): the unique identifier for this Export. Use this identifier when checking the export job's status
               created_at (string): the date and time that the export job was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               type (string): the type of the export job
               finished_at (string): the date and time that the export job was finished as a UTC string in YYYY-MM-DD HH:MM:SS format, or null for jobs that have not run
               state (string): the export job's state
               result_url (string): the url for the export job's results, if the job is complete

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'notify_email': notify_email}
        return self.master.call('exports/rejects', _params)

    def whitelist(self, notify_email=None):
        """Begins an export of your rejection whitelist. The whitelist will be exported to a zip archive
containing a single file named whitelist.csv that includes the following fields:
email, detail, created_at.

        Args:
           notify_email (string): an optional email address to notify when the export job has finished.

        Returns:
           struct.  information about the whitelist export job that was started::
               id (string): the unique identifier for this Export. Use this identifier when checking the export job's status
               created_at (string): the date and time that the export job was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               type (string): the type of the export job
               finished_at (string): the date and time that the export job was finished as a UTC string in YYYY-MM-DD HH:MM:SS format, or null for jobs that have not run
               state (string): the export job's state
               result_url (string): the url for the export job's results, if the job is complete

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'notify_email': notify_email}
        return self.master.call('exports/whitelist', _params)

    def activity(self, notify_email=None, date_from=None, date_to=None, tags=None, senders=None, states=None):
        """Begins an export of your activity history. The activity will be exported to a zaip archive
containing a single file named activity.csv in the same format as you would be able to export
from your account's activity view. It includes the following fields: Date, Email Address,
Sender, Subject, Status, Tags, Opens, Clicks, Bounce Detail. If you have configured any custom
metadata fields, they will be included in the exported data.

        Args:
           notify_email (string): an optional email address to notify when the export job has finished
           date_from (string): start date as a UTC string in YYYY-MM-DD HH:MM:SS format
           date_to (string): end date as a UTC string in YYYY-MM-DD HH:MM:SS format
           tags (array): an array of tag names to narrow the export to; will match messages that contain ANY of the tags::
               tags[] (string): a tag name
           senders (array): an array of senders to narrow the export to::
               senders[] (string): a sender address
           states (array): an array of states to narrow the export to; messages with ANY of the states will be included::
               states[] (string): a message state

        Returns:
           struct.  information about the activity export job that was started::
               id (string): the unique identifier for this Export. Use this identifier when checking the export job's status
               created_at (string): the date and time that the export job was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               type (string): the type of the export job
               finished_at (string): the date and time that the export job was finished as a UTC string in YYYY-MM-DD HH:MM:SS format, or null for jobs that have not run
               state (string): the export job's state
               result_url (string): the url for the export job's results, if the job is complete

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'notify_email': notify_email, 'date_from': date_from, 'date_to': date_to, 'tags': tags, 'senders': senders, 'states': states}
        return self.master.call('exports/activity', _params)


class Users(object):
    def __init__(self, master):
        self.master = master

    def info(self, ):
        """Return the information about the API-connected user

        Returns:
           struct.  the user information including username, key, reputation, quota, and historical sending stats::
               username (string): the username of the user (used for SMTP authentication)
               created_at (string): the date and time that the user's Mandrill account was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               public_id (string): a unique, permanent identifier for this user
               reputation (integer): the reputation of the user on a scale from 0 to 100, with 75 generally being a "good" reputation
               hourly_quota (integer): the maximum number of emails Mandrill will deliver for this user each hour.  Any emails beyond that will be accepted and queued for later delivery.  Users with higher reputations will have higher hourly quotas
               backlog (integer): the number of emails that are queued for delivery due to exceeding your monthly or hourly quotas
               stats (struct): an aggregate summary of the account's sending stats::
                   stats.today (struct): stats for this user so far today::
                       stats.today.sent (integer): the number of emails sent for this user so far today
                       stats.today.hard_bounces (integer): the number of emails hard bounced for this user so far today
                       stats.today.soft_bounces (integer): the number of emails soft bounced for this user so far today
                       stats.today.rejects (integer): the number of emails rejected for sending this user so far today
                       stats.today.complaints (integer): the number of spam complaints for this user so far today
                       stats.today.unsubs (integer): the number of unsubscribes for this user so far today
                       stats.today.opens (integer): the number of times emails have been opened for this user so far today
                       stats.today.unique_opens (integer): the number of unique opens for emails sent for this user so far today
                       stats.today.clicks (integer): the number of URLs that have been clicked for this user so far today
                       stats.today.unique_clicks (integer): the number of unique clicks for emails sent for this user so far today

                   stats.last_7_days (struct): stats for this user in the last 7 days::
                       stats.last_7_days.sent (integer): the number of emails sent for this user in the last 7 days
                       stats.last_7_days.hard_bounces (integer): the number of emails hard bounced for this user in the last 7 days
                       stats.last_7_days.soft_bounces (integer): the number of emails soft bounced for this user in the last 7 days
                       stats.last_7_days.rejects (integer): the number of emails rejected for sending this user in the last 7 days
                       stats.last_7_days.complaints (integer): the number of spam complaints for this user in the last 7 days
                       stats.last_7_days.unsubs (integer): the number of unsubscribes for this user in the last 7 days
                       stats.last_7_days.opens (integer): the number of times emails have been opened for this user in the last 7 days
                       stats.last_7_days.unique_opens (integer): the number of unique opens for emails sent for this user in the last 7 days
                       stats.last_7_days.clicks (integer): the number of URLs that have been clicked for this user in the last 7 days
                       stats.last_7_days.unique_clicks (integer): the number of unique clicks for emails sent for this user in the last 7 days

                   stats.last_30_days (struct): stats for this user in the last 30 days::
                       stats.last_30_days.sent (integer): the number of emails sent for this user in the last 30 days
                       stats.last_30_days.hard_bounces (integer): the number of emails hard bounced for this user in the last 30 days
                       stats.last_30_days.soft_bounces (integer): the number of emails soft bounced for this user in the last 30 days
                       stats.last_30_days.rejects (integer): the number of emails rejected for sending this user in the last 30 days
                       stats.last_30_days.complaints (integer): the number of spam complaints for this user in the last 30 days
                       stats.last_30_days.unsubs (integer): the number of unsubscribes for this user in the last 30 days
                       stats.last_30_days.opens (integer): the number of times emails have been opened for this user in the last 30 days
                       stats.last_30_days.unique_opens (integer): the number of unique opens for emails sent for this user in the last 30 days
                       stats.last_30_days.clicks (integer): the number of URLs that have been clicked for this user in the last 30 days
                       stats.last_30_days.unique_clicks (integer): the number of unique clicks for emails sent for this user in the last 30 days

                   stats.last_60_days (struct): stats for this user in the last 60 days::
                       stats.last_60_days.sent (integer): the number of emails sent for this user in the last 60 days
                       stats.last_60_days.hard_bounces (integer): the number of emails hard bounced for this user in the last 60 days
                       stats.last_60_days.soft_bounces (integer): the number of emails soft bounced for this user in the last 60 days
                       stats.last_60_days.rejects (integer): the number of emails rejected for sending this user in the last 60 days
                       stats.last_60_days.complaints (integer): the number of spam complaints for this user in the last 60 days
                       stats.last_60_days.unsubs (integer): the number of unsubscribes for this user in the last 60 days
                       stats.last_60_days.opens (integer): the number of times emails have been opened for this user in the last 60 days
                       stats.last_60_days.unique_opens (integer): the number of unique opens for emails sent for this user in the last 60 days
                       stats.last_60_days.clicks (integer): the number of URLs that have been clicked for this user in the last 60 days
                       stats.last_60_days.unique_clicks (integer): the number of unique clicks for emails sent for this user in the last 60 days

                   stats.last_90_days (struct): stats for this user in the last 90 days::
                       stats.last_90_days.sent (integer): the number of emails sent for this user in the last 90 days
                       stats.last_90_days.hard_bounces (integer): the number of emails hard bounced for this user in the last 90 days
                       stats.last_90_days.soft_bounces (integer): the number of emails soft bounced for this user in the last 90 days
                       stats.last_90_days.rejects (integer): the number of emails rejected for sending this user in the last 90 days
                       stats.last_90_days.complaints (integer): the number of spam complaints for this user in the last 90 days
                       stats.last_90_days.unsubs (integer): the number of unsubscribes for this user in the last 90 days
                       stats.last_90_days.opens (integer): the number of times emails have been opened for this user in the last 90 days
                       stats.last_90_days.unique_opens (integer): the number of unique opens for emails sent for this user in the last 90 days
                       stats.last_90_days.clicks (integer): the number of URLs that have been clicked for this user in the last 90 days
                       stats.last_90_days.unique_clicks (integer): the number of unique clicks for emails sent for this user in the last 90 days

                   stats.all_time (struct): stats for the lifetime of the user's account::
                       stats.all_time.sent (integer): the number of emails sent in the lifetime of the user's account
                       stats.all_time.hard_bounces (integer): the number of emails hard bounced in the lifetime of the user's account
                       stats.all_time.soft_bounces (integer): the number of emails soft bounced in the lifetime of the user's account
                       stats.all_time.rejects (integer): the number of emails rejected for sending this user so far today
                       stats.all_time.complaints (integer): the number of spam complaints in the lifetime of the user's account
                       stats.all_time.unsubs (integer): the number of unsubscribes in the lifetime of the user's account
                       stats.all_time.opens (integer): the number of times emails have been opened in the lifetime of the user's account
                       stats.all_time.unique_opens (integer): the number of unique opens for emails sent in the lifetime of the user's account
                       stats.all_time.clicks (integer): the number of URLs that have been clicked in the lifetime of the user's account
                       stats.all_time.unique_clicks (integer): the number of unique clicks for emails sent in the lifetime of the user's account



        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('users/info', _params)

    def ping(self, ):
        """Validate an API key and respond to a ping

        Returns:
           string.  the string "PONG!"

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('users/ping', _params)

    def ping2(self, ):
        """Validate an API key and respond to a ping (anal JSON parser version)

        Returns:
           struct.  a struct with one key "PING" with a static value "PONG!"

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('users/ping2', _params)

    def senders(self, ):
        """Return the senders that have tried to use this account, both verified and unverified

        Returns:
           array.  an array of sender data, one for each sending addresses used by the account::
               [] (struct): the information on each sending address in the account::
                   [].address (string): the sender's email address
                   [].created_at (string): the date and time that the sender was first seen by Mandrill as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the total number of messages sent by this sender
                   [].hard_bounces (integer): the total number of hard bounces by messages by this sender
                   [].soft_bounces (integer): the total number of soft bounces by messages by this sender
                   [].rejects (integer): the total number of rejected messages by this sender
                   [].complaints (integer): the total number of spam complaints received for messages by this sender
                   [].unsubs (integer): the total number of unsubscribe requests received for messages by this sender
                   [].opens (integer): the total number of times messages by this sender have been opened
                   [].clicks (integer): the total number of times tracked URLs in messages by this sender have been clicked


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('users/senders', _params)


class Rejects(object):
    def __init__(self, master):
        self.master = master

    def add(self, email):
        """Adds an email to your email rejection blacklist. Addresses that you
add manually will never expire and there is no reputation penalty
for removing them from your blacklist. Attempting to blacklist an
address that has been whitelisted will have no effect.

        Args:
           email (string): an email address to block

        Returns:
           struct.  a status object containing the address and the result of the operation::
               email (string): the email address you provided
               added (boolean): whether the operation succeeded

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email}
        return self.master.call('rejects/add', _params)

    def list(self, email=None, include_expired=False):
        """Retrieves your email rejection blacklist. You can provide an email
address to limit the results. Returns up to 1000 results. By default,
entries that have expired are excluded from the results; set
include_expired to true to include them.

        Args:
           email (string): an optional email address to search by
           include_expired (boolean): whether to include rejections that have already expired.

        Returns:
           array.  Up to 1000 rejection entries::
               [] (struct): the information for each rejection blacklist entry::
                   [].email (string): the email that is blocked
                   [].reason (string): the type of event (hard-bounce, soft-bounce, spam, unsub) that caused this rejection
                   [].detail (string): extended details about the event, such as the SMTP diagnostic for bounces or the comment for manually-created rejections
                   [].created_at (string): when the email was added to the blacklist
                   [].last_event_at (string): the timestamp of the most recent event that either created or renewed this rejection
                   [].expires_at (string): when the blacklist entry will expire (this may be in the past)
                   [].expired (boolean): whether the blacklist entry has expired
                   [].sender (struct): the sender that this blacklist entry applies to, or null if none.::
                       [].sender.address (string): the sender's email address
                       [].sender.created_at (string): the date and time that the sender was first seen by Mandrill as a UTC date string in YYYY-MM-DD HH:MM:SS format
                       [].sender.sent (integer): the total number of messages sent by this sender
                       [].sender.hard_bounces (integer): the total number of hard bounces by messages by this sender
                       [].sender.soft_bounces (integer): the total number of soft bounces by messages by this sender
                       [].sender.rejects (integer): the total number of rejected messages by this sender
                       [].sender.complaints (integer): the total number of spam complaints received for messages by this sender
                       [].sender.unsubs (integer): the total number of unsubscribe requests received for messages by this sender
                       [].sender.opens (integer): the total number of times messages by this sender have been opened
                       [].sender.clicks (integer): the total number of times tracked URLs in messages by this sender have been clicked



        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email, 'include_expired': include_expired}
        return self.master.call('rejects/list', _params)

    def delete(self, email):
        """Deletes an email rejection. There is no limit to how many rejections
you can remove from your blacklist, but keep in mind that each deletion
has an affect on your reputation.

        Args:
           email (string): an email address

        Returns:
           struct.  a status object containing the address and whether the deletion succeeded.::
               email (string): the email address that was removed from the blacklist
               deleted (boolean): whether the address was deleted successfully.

        Raises:
           InvalidRejectError: The requested email is not in the rejection list
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email}
        return self.master.call('rejects/delete', _params)


class Inbound(object):
    def __init__(self, master):
        self.master = master

    def domains(self, ):
        """List the domains that have been configured for inbound delivery

        Returns:
           array.  the inbound domains associated with the account::
               [] (struct): the individual domain info::
                   [].domain (string): the domain name that is accepting mail
                   [].created_at (string): the date and time that the inbound domain was added as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].valid_mx (boolean): true if this inbound domain has successfully set up an MX record to deliver mail to the Mandrill servers


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('inbound/domains', _params)

    def routes(self, domain):
        """List the mailbox routes defined for an inbound domain

        Args:
           domain (string): the domain to check

        Returns:
           array.  the routes associated with the domain::
               [] (struct): the individual mailbox route::
                   [].pattern (string): the search pattern that the mailbox name should match
                   [].url (string): the webhook URL where inbound messages will be published


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           UnknownInboundDomainError: The requested inbound domain does not exist
           Error: A general Mandrill error has occurred
        """
        _params = {'domain': domain}
        return self.master.call('inbound/routes', _params)

    def send_raw(self, raw_message, to=None, mail_from=None, helo=None, client_address=None):
        """Take a raw MIME document destined for a domain with inbound domains set up, and send it to the inbound hook exactly as if it had been sent over SMTP

        Args:
           raw_message (string): the full MIME document of an email message
           to (array|null): optionally define the recipients to receive the message - otherwise we'll use the To, Cc, and Bcc headers provided in the document::
               to[] (string): the email address of the recipient
           mail_from (string): the address specified in the MAIL FROM stage of the SMTP conversation. Required for the SPF check.
           helo (string): the identification provided by the client mta in the MTA state of the SMTP conversation. Required for the SPF check.
           client_address (string): the remote MTA's ip address. Optional; required for the SPF check.

        Returns:
           array.  an array of the information for each recipient in the message (usually one) that matched an inbound route::
               [] (struct): the individual recipient information::
                   [].email (string): the email address of the matching recipient
                   [].pattern (string): the mailbox route pattern that the recipient matched
                   [].url (string): the webhook URL that the message was posted to


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'raw_message': raw_message, 'to': to, 'mail_from': mail_from, 'helo': helo, 'client_address': client_address}
        return self.master.call('inbound/send-raw', _params)


class Tags(object):
    def __init__(self, master):
        self.master = master

    def list(self, ):
        """Return all of the user-defined tag information

        Returns:
           array.  a list of user-defined tags::
               [] (struct): a user-defined tag::
                   [].tag (string): the actual tag as a string
                   [].sent (integer): the total number of messages sent with this tag
                   [].hard_bounces (integer): the total number of hard bounces by messages with this tag
                   [].soft_bounces (integer): the total number of soft bounces by messages with this tag
                   [].rejects (integer): the total number of rejected messages with this tag
                   [].complaints (integer): the total number of spam complaints received for messages with this tag
                   [].unsubs (integer): the total number of unsubscribe requests received for messages with this tag
                   [].opens (integer): the total number of times messages with this tag have been opened
                   [].clicks (integer): the total number of times tracked URLs in messages with this tag have been clicked


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('tags/list', _params)

    def delete(self, tag):
        """Deletes a tag permanently. Deleting a tag removes the tag from any messages
that have been sent, and also deletes the tag's stats. There is no way to
undo this operation, so use it carefully.

        Args:
           tag (string): a tag name

        Returns:
           struct.  the tag that was deleted::
               tag (string): the actual tag as a string
               sent (integer): the total number of messages sent with this tag
               hard_bounces (integer): the total number of hard bounces by messages with this tag
               soft_bounces (integer): the total number of soft bounces by messages with this tag
               rejects (integer): the total number of rejected messages with this tag
               complaints (integer): the total number of spam complaints received for messages with this tag
               unsubs (integer): the total number of unsubscribe requests received for messages with this tag
               opens (integer): the total number of times messages with this tag have been opened
               clicks (integer): the total number of times tracked URLs in messages with this tag have been clicked

        Raises:
           InvalidTagNameError: The requested tag does not exist or contains invalid characters
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'tag': tag}
        return self.master.call('tags/delete', _params)

    def info(self, tag):
        """Return more detailed information about a single tag, including aggregates of recent stats

        Args:
           tag (string): an existing tag name

        Returns:
           struct.  the detailed information on the tag::
               tag (string): the actual tag as a string
               sent (integer): the total number of messages sent with this tag
               hard_bounces (integer): the total number of hard bounces by messages with this tag
               soft_bounces (integer): the total number of soft bounces by messages with this tag
               rejects (integer): the total number of rejected messages with this tag
               complaints (integer): the total number of spam complaints received for messages with this tag
               unsubs (integer): the total number of unsubscribe requests received for messages with this tag
               opens (integer): the total number of times messages with this tag have been opened
               clicks (integer): the total number of times tracked URLs in messages with this tag have been clicked
               stats (struct): an aggregate summary of the tag's sending stats::
                   stats.today (struct): stats with this tag so far today::
                       stats.today.sent (integer): the number of emails sent with this tag so far today
                       stats.today.hard_bounces (integer): the number of emails hard bounced with this tag so far today
                       stats.today.soft_bounces (integer): the number of emails soft bounced with this tag so far today
                       stats.today.rejects (integer): the number of emails rejected for sending this tag so far today
                       stats.today.complaints (integer): the number of spam complaints with this tag so far today
                       stats.today.unsubs (integer): the number of unsubscribes with this tag so far today
                       stats.today.opens (integer): the number of times emails have been opened with this tag so far today
                       stats.today.unique_opens (integer): the number of unique opens for emails sent with this tag so far today
                       stats.today.clicks (integer): the number of URLs that have been clicked with this tag so far today
                       stats.today.unique_clicks (integer): the number of unique clicks for emails sent with this tag so far today

                   stats.last_7_days (struct): stats with this tag in the last 7 days::
                       stats.last_7_days.sent (integer): the number of emails sent with this tag in the last 7 days
                       stats.last_7_days.hard_bounces (integer): the number of emails hard bounced with this tag in the last 7 days
                       stats.last_7_days.soft_bounces (integer): the number of emails soft bounced with this tag in the last 7 days
                       stats.last_7_days.rejects (integer): the number of emails rejected for sending this tag in the last 7 days
                       stats.last_7_days.complaints (integer): the number of spam complaints with this tag in the last 7 days
                       stats.last_7_days.unsubs (integer): the number of unsubscribes with this tag in the last 7 days
                       stats.last_7_days.opens (integer): the number of times emails have been opened with this tag in the last 7 days
                       stats.last_7_days.unique_opens (integer): the number of unique opens for emails sent with this tag in the last 7 days
                       stats.last_7_days.clicks (integer): the number of URLs that have been clicked with this tag in the last 7 days
                       stats.last_7_days.unique_clicks (integer): the number of unique clicks for emails sent with this tag in the last 7 days

                   stats.last_30_days (struct): stats with this tag in the last 30 days::
                       stats.last_30_days.sent (integer): the number of emails sent with this tag in the last 30 days
                       stats.last_30_days.hard_bounces (integer): the number of emails hard bounced with this tag in the last 30 days
                       stats.last_30_days.soft_bounces (integer): the number of emails soft bounced with this tag in the last 30 days
                       stats.last_30_days.rejects (integer): the number of emails rejected for sending this tag in the last 30 days
                       stats.last_30_days.complaints (integer): the number of spam complaints with this tag in the last 30 days
                       stats.last_30_days.unsubs (integer): the number of unsubscribes with this tag in the last 30 days
                       stats.last_30_days.opens (integer): the number of times emails have been opened with this tag in the last 30 days
                       stats.last_30_days.unique_opens (integer): the number of unique opens for emails sent with this tag in the last 30 days
                       stats.last_30_days.clicks (integer): the number of URLs that have been clicked with this tag in the last 30 days
                       stats.last_30_days.unique_clicks (integer): the number of unique clicks for emails sent with this tag in the last 30 days

                   stats.last_60_days (struct): stats with this tag in the last 60 days::
                       stats.last_60_days.sent (integer): the number of emails sent with this tag in the last 60 days
                       stats.last_60_days.hard_bounces (integer): the number of emails hard bounced with this tag in the last 60 days
                       stats.last_60_days.soft_bounces (integer): the number of emails soft bounced with this tag in the last 60 days
                       stats.last_60_days.rejects (integer): the number of emails rejected for sending this tag in the last 60 days
                       stats.last_60_days.complaints (integer): the number of spam complaints with this tag in the last 60 days
                       stats.last_60_days.unsubs (integer): the number of unsubscribes with this tag in the last 60 days
                       stats.last_60_days.opens (integer): the number of times emails have been opened with this tag in the last 60 days
                       stats.last_60_days.unique_opens (integer): the number of unique opens for emails sent with this tag in the last 60 days
                       stats.last_60_days.clicks (integer): the number of URLs that have been clicked with this tag in the last 60 days
                       stats.last_60_days.unique_clicks (integer): the number of unique clicks for emails sent with this tag in the last 60 days

                   stats.last_90_days (struct): stats with this tag in the last 90 days::
                       stats.last_90_days.sent (integer): the number of emails sent with this tag in the last 90 days
                       stats.last_90_days.hard_bounces (integer): the number of emails hard bounced with this tag in the last 90 days
                       stats.last_90_days.soft_bounces (integer): the number of emails soft bounced with this tag in the last 90 days
                       stats.last_90_days.rejects (integer): the number of emails rejected for sending this tag in the last 90 days
                       stats.last_90_days.complaints (integer): the number of spam complaints with this tag in the last 90 days
                       stats.last_90_days.unsubs (integer): the number of unsubscribes with this tag in the last 90 days
                       stats.last_90_days.opens (integer): the number of times emails have been opened with this tag in the last 90 days
                       stats.last_90_days.unique_opens (integer): the number of unique opens for emails sent with this tag in the last 90 days
                       stats.last_90_days.clicks (integer): the number of URLs that have been clicked with this tag in the last 90 days
                       stats.last_90_days.unique_clicks (integer): the number of unique clicks for emails sent with this tag in the last 90 days



        Raises:
           InvalidTagNameError: The requested tag does not exist or contains invalid characters
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'tag': tag}
        return self.master.call('tags/info', _params)

    def time_series(self, tag):
        """Return the recent history (hourly stats for the last 30 days) for a tag

        Args:
           tag (string): an existing tag name

        Returns:
           array.  the array of history information::
               [] (struct): the stats for a single hour::
                   [].time (string): the hour as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the number of emails that were sent during the hour
                   [].hard_bounces (integer): the number of emails that hard bounced during the hour
                   [].soft_bounces (integer): the number of emails that soft bounced during the hour
                   [].rejects (integer): the number of emails that were rejected during the hour
                   [].complaints (integer): the number of spam complaints received during the hour
                   [].unsubs (integer): the number of unsubscribes received during the hour
                   [].opens (integer): the number of emails opened during the hour
                   [].unique_opens (integer): the number of unique opens generated by messages sent during the hour
                   [].clicks (integer): the number of tracked URLs clicked during the hour
                   [].unique_clicks (integer): the number of unique clicks generated by messages sent during the hour


        Raises:
           InvalidTagNameError: The requested tag does not exist or contains invalid characters
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'tag': tag}
        return self.master.call('tags/time-series', _params)

    def all_time_series(self, ):
        """Return the recent history (hourly stats for the last 30 days) for all tags

        Returns:
           array.  the array of history information::
               [] (struct): the stats for a single hour::
                   [].time (string): the hour as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the number of emails that were sent during the hour
                   [].hard_bounces (integer): the number of emails that hard bounced during the hour
                   [].soft_bounces (integer): the number of emails that soft bounced during the hour
                   [].rejects (integer): the number of emails that were rejected during the hour
                   [].complaints (integer): the number of spam complaints received during the hour
                   [].unsubs (integer): the number of unsubscribes received during the hour
                   [].opens (integer): the number of emails opened during the hour
                   [].unique_opens (integer): the number of unique opens generated by messages sent during the hour
                   [].clicks (integer): the number of tracked URLs clicked during the hour
                   [].unique_clicks (integer): the number of unique clicks generated by messages sent during the hour


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('tags/all-time-series', _params)


class Messages(object):
    def __init__(self, master):
        self.master = master

    def send(self, message, async=False):
        """Send a new transactional message through Mandrill

        Args:
           message (struct): the information on the message to send::
               message.html (string): the full HTML content to be sent
               message.text (string): optional full text content to be sent
               message.subject (string): the message subject
               message.from_email (string): the sender email address.
               message.from_name (string): optional from name to be used
               message.to (array): an array of recipient information.::
                   message.to[] (struct): a single recipient's information.::
                       message.to[].email (string): the email address of the recipient
                       message.to[].name (string): the optional display name to use for the recipient


               message.headers (struct): optional extra headers to add to the message (currently only Reply-To and X-* headers are allowed)
               message.important (boolean): whether or not this message is important, and should be delivered ahead of non-important messages
               message.track_opens (boolean): whether or not to turn on open tracking for the message
               message.track_clicks (boolean): whether or not to turn on click tracking for the message
               message.auto_text (boolean): whether or not to automatically generate a text part for messages that are not given text
               message.auto_html (boolean): whether or not to automatically generate an HTML part for messages that are not given HTML
               message.inline_css (boolean): whether or not to automatically inline all CSS styles provided in the message HTML - only for HTML documents less than 256KB in size
               message.url_strip_qs (boolean): whether or not to strip the query string from URLs when aggregating tracked URL data
               message.preserve_recipients (boolean): whether or not to expose all recipients in to "To" header for each email
               message.bcc_address (string): an optional address to receive an exact copy of each recipient's email
               message.tracking_domain (string): a custom domain to use for tracking opens and clicks instead of mandrillapp.com
               message.signing_domain (string): a custom domain to use for SPF/DKIM signing instead of mandrill (for "via" or "on behalf of" in email clients)
               message.merge (boolean): whether to evaluate merge tags in the message. Will automatically be set to true if either merge_vars or global_merge_vars are provided.
               message.global_merge_vars (array): global merge variables to use for all recipients. You can override these per recipient.::
                   message.global_merge_vars[] (struct): a single global merge variable::
                       message.global_merge_vars[].name (string): the global merge variable's name. Merge variable names are case-insensitive and may not start with _
                       message.global_merge_vars[].content (string): the global merge variable's content


               message.merge_vars (array): per-recipient merge variables, which override global merge variables with the same name.::
                   message.merge_vars[] (struct): per-recipient merge variables::
                       message.merge_vars[].rcpt (string): the email address of the recipient that the merge variables should apply to
                       message.merge_vars[].vars (array): the recipient's merge variables::
                           message.merge_vars[].vars[] (struct): a single merge variable::
                               message.merge_vars[].vars[].name (string): the merge variable's name. Merge variable names are case-insensitive and may not start with _
                               message.merge_vars[].vars[].content (string): the merge variable's content




               message.tags (array): an array of string to tag the message with.  Stats are accumulated using tags, though we only store the first 100 we see, so this should not be unique or change frequently.  Tags should be 50 characters or less.  Any tags starting with an underscore are reserved for internal use and will cause errors.::
                   message.tags[] (string): a single tag - must not start with an underscore

               message.google_analytics_domains (array): an array of strings indicating for which any matching URLs will automatically have Google Analytics parameters appended to their query string automatically.
               message.google_analytics_campaign (array|string): optional string indicating the value to set for the utm_campaign tracking parameter. If this isn't provided the email's from address will be used instead.
               message.metadata (array): metadata an associative array of user metadata. Mandrill will store this metadata and make it available for retrieval. In addition, you can select up to 10 metadata fields to index and make searchable using the Mandrill search api.
               message.recipient_metadata (array): Per-recipient metadata that will override the global values specified in the metadata parameter.::
                   message.recipient_metadata[] (struct): metadata for a single recipient::
                       message.recipient_metadata[].rcpt (string): the email address of the recipient that the metadata is associated with
                       message.recipient_metadata[].values (array): an associated array containing the recipient's unique metadata. If a key exists in both the per-recipient metadata and the global metadata, the per-recipient metadata will be used.


               message.attachments (array): an array of supported attachments to add to the message::
                   message.attachments[] (struct): a single supported attachment::
                       message.attachments[].type (string): the MIME type of the attachment
                       message.attachments[].name (string): the file name of the attachment
                       message.attachments[].content (string): the content of the attachment as a base64-encoded string


               message.images (array): an array of embedded images to add to the message::
                   message.images[] (struct): a single embedded image::
                       message.images[].type (string): the MIME type of the image - must start with "image/"
                       message.images[].name (string): the Content ID of the image - use <img src="cid:THIS_VALUE"> to reference the image in your HTML content
                       message.images[].content (string): the content of the image as a base64-encoded string


           async (boolean): enable a background sending mode that is optimized for bulk sending. In async mode, messages/send will immediately return a status of "queued" for every recipient. To handle rejections when sending in async mode, set up a webhook for the 'reject' event. Defaults to false for messages with no more than 10 recipients; messages with more than 10 recipients are always sent asynchronously, regardless of the value of async.

        Returns:
           array.  of structs for each recipient containing the key "email" with the email address and "status" as either "sent", "queued", or "rejected"::
               [] (struct): the sending results for a single recipient::
                   [].email (string): the email address of the recipient
                   [].status (string): the sending status of the recipient - either "sent", "queued", "rejected", or "invalid"
                   [].reject_reason (string): the reason for the rejection if the recipient status is "rejected"
                   []._id (string): the message's unique id


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'message': message, 'async': async}
        return self.master.call('messages/send', _params)

    def send_template(self, template_name, template_content, message, async=False):
        """Send a new transactional message through Mandrill using a template

        Args:
           template_name (string): the immutable name or slug of a template that exists in the user's account. For backwards-compatibility, the template name may also be used but the immutable slug is preferred.
           template_content (array): an array of template content to send.  Each item in the array should be a struct with two keys - name: the name of the content block to set the content for, and content: the actual content to put into the block::
               template_content[] (struct): the injection of a single piece of content into a single editable region::
                   template_content[].name (string): the name of the mc:edit editable region to inject into
                   template_content[].content (string): the content to inject

           message (struct): the other information on the message to send - same as /messages/send, but without the html content::
               message.html (string): optional full HTML content to be sent if not in template
               message.text (string): optional full text content to be sent
               message.subject (string): the message subject
               message.from_email (string): the sender email address.
               message.from_name (string): optional from name to be used
               message.to (array): an array of recipient information.::
                   message.to[] (struct): a single recipient's information.::
                       message.to[].email (string): the email address of the recipient
                       message.to[].name (string): the optional display name to use for the recipient


               message.headers (struct): optional extra headers to add to the message (currently only Reply-To and X-* headers are allowed)
               message.important (boolean): whether or not this message is important, and should be delivered ahead of non-important messages
               message.track_opens (boolean): whether or not to turn on open tracking for the message
               message.track_clicks (boolean): whether or not to turn on click tracking for the message
               message.auto_text (boolean): whether or not to automatically generate a text part for messages that are not given text
               message.auto_html (boolean): whether or not to automatically generate an HTML part for messages that are not given HTML
               message.inline_css (boolean): whether or not to automatically inline all CSS styles provided in the message HTML - only for HTML documents less than 256KB in size
               message.url_strip_qs (boolean): whether or not to strip the query string from URLs when aggregating tracked URL data
               message.preserve_recipients (boolean): whether or not to expose all recipients in to "To" header for each email
               message.bcc_address (string): an optional address to receive an exact copy of each recipient's email
               message.tracking_domain (string): a custom domain to use for tracking opens and clicks instead of mandrillapp.com
               message.signing_domain (string): a custom domain to use for SPF/DKIM signing instead of mandrill (for "via" or "on behalf of" in email clients)
               message.merge (boolean): whether to evaluate merge tags in the message. Will automatically be set to true if either merge_vars or global_merge_vars are provided.
               message.global_merge_vars (array): global merge variables to use for all recipients. You can override these per recipient.::
                   message.global_merge_vars[] (struct): a single global merge variable::
                       message.global_merge_vars[].name (string): the global merge variable's name. Merge variable names are case-insensitive and may not start with _
                       message.global_merge_vars[].content (string): the global merge variable's content


               message.merge_vars (array): per-recipient merge variables, which override global merge variables with the same name.::
                   message.merge_vars[] (struct): per-recipient merge variables::
                       message.merge_vars[].rcpt (string): the email address of the recipient that the merge variables should apply to
                       message.merge_vars[].vars (array): the recipient's merge variables::
                           message.merge_vars[].vars[] (struct): a single merge variable::
                               message.merge_vars[].vars[].name (string): the merge variable's name. Merge variable names are case-insensitive and may not start with _
                               message.merge_vars[].vars[].content (string): the merge variable's content




               message.tags (array): an array of string to tag the message with.  Stats are accumulated using tags, though we only store the first 100 we see, so this should not be unique or change frequently.  Tags should be 50 characters or less.  Any tags starting with an underscore are reserved for internal use and will cause errors.::
                   message.tags[] (string): a single tag - must not start with an underscore

               message.google_analytics_domains (array): an array of strings indicating for which any matching URLs will automatically have Google Analytics parameters appended to their query string automatically.
               message.google_analytics_campaign (array|string): optional string indicating the value to set for the utm_campaign tracking parameter. If this isn't provided the email's from address will be used instead.
               message.metadata (array): metadata an associative array of user metadata. Mandrill will store this metadata and make it available for retrieval. In addition, you can select up to 10 metadata fields to index and make searchable using the Mandrill search api.
               message.recipient_metadata (array): Per-recipient metadata that will override the global values specified in the metadata parameter.::
                   message.recipient_metadata[] (struct): metadata for a single recipient::
                       message.recipient_metadata[].rcpt (string): the email address of the recipient that the metadata is associated with
                       message.recipient_metadata[].values (array): an associated array containing the recipient's unique metadata. If a key exists in both the per-recipient metadata and the global metadata, the per-recipient metadata will be used.


               message.attachments (array): an array of supported attachments to add to the message::
                   message.attachments[] (struct): a single supported attachment::
                       message.attachments[].type (string): the MIME type of the attachment
                       message.attachments[].name (string): the file name of the attachment
                       message.attachments[].content (string): the content of the attachment as a base64-encoded string


               message.images (array): an array of embedded images to add to the message::
                   message.images[] (struct): a single embedded image::
                       message.images[].type (string): the MIME type of the image - must start with "image/"
                       message.images[].name (string): the Content ID of the image - use <img src="cid:THIS_VALUE"> to reference the image in your HTML content
                       message.images[].content (string): the content of the image as a base64-encoded string


           async (boolean): enable a background sending mode that is optimized for bulk sending. In async mode, messages/send will immediately return a status of "queued" for every recipient. To handle rejections when sending in async mode, set up a webhook for the 'reject' event. Defaults to false for messages with no more than 10 recipients; messages with more than 10 recipients are always sent asynchronously, regardless of the value of async.

        Returns:
           array.  of structs for each recipient containing the key "email" with the email address and "status" as either "sent", "queued", or "rejected"::
               [] (struct): the sending results for a single recipient::
                   [].email (string): the email address of the recipient
                   [].status (string): the sending status of the recipient - either "sent", "queued", "rejected", or "invalid"
                   [].reject_reason (string): the reason for the rejection if the recipient status is "rejected"
                   []._id (string): the message's unique id


        Raises:
           UnknownTemplateError: The requested template does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'template_name': template_name, 'template_content': template_content, 'message': message, 'async': async}
        return self.master.call('messages/send-template', _params)

    def search(self, query='*', date_from=None, date_to=None, tags=None, senders=None, limit=100):
        """Search the content of recently sent messages and optionally narrow by date range, tags and senders

        Args:
           query (string): the search terms to find matching messages for
           date_from (string): start date
           date_to (string): end date
           tags (array): an array of tag names to narrow the search to, will return messages that contain ANY of the tags
           senders (array): an array of sender addresses to narrow the search to, will return messages sent by ANY of the senders
           limit (integer): the maximum number of results to return, defaults to 100, 1000 is the maximum

        Returns:
           array.  of structs for each matching message::
               [] (struct): the information for a single matching message::
                   [].ts (integer): the Unix timestamp from when this message was sent
                   []._id (string): the message's unique id
                   [].sender (string): the email address of the sender
                   [].subject (string): the message's subject link
                   [].email (string): the recipient email address
                   [].tags (array): list of tags on this message::
                       [].tags[] (string): individual tag on this message

                   [].opens (integer): how many times has this message been opened
                   [].clicks (integer): how many times has a link been clicked in this message
                   [].state (string): sending status of this message: sent, bounced, rejected
                   [].metadata (struct): any custom metadata provided when the message was sent


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'query': query, 'date_from': date_from, 'date_to': date_to, 'tags': tags, 'senders': senders, 'limit': limit}
        return self.master.call('messages/search', _params)

    def parse(self, raw_message):
        """Parse the full MIME document for an email message, returning the content of the message broken into its constituent pieces

        Args:
           raw_message (string): the full MIME document of an email message

        Returns:
           struct.  the parsed message::
               subject (string): the subject of the message
               from_email (string): the email address of the sender
               from_name (string): the alias of the sender (if any)
               to (array): an array of any recipients in the message::
                   to[] (struct): the information on a single recipient::
                       to[].email (string): the email address of the recipient
                       to[].name (string): the alias of the recipient (if any)


               headers (struct): the key-value pairs of the MIME headers for the message's main document
               text (string): the text part of the message, if any
               html (string): the HTML part of the message, if any
               attachments (array): an array of any attachments that can be found in the message::
                   attachments[] (struct): information about an individual attachment::
                       attachments[].name (string): the file name of the attachment
                       attachments[].type (string): the MIME type of the attachment
                       attachments[].binary (boolean): if this is set to true, the attachment is not pure-text, and the content will be base64 encoded
                       attachments[].content (string): the content of the attachment as a text string or a base64 encoded string based on the attachment type


               images (array): an array of any embedded images that can be found in the message::
                   images[] (struct): information about an individual image::
                       images[].name (string): the Content-ID of the embedded image
                       images[].type (string): the MIME type of the image
                       images[].content (string): the content of the image as a base64 encoded string



        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'raw_message': raw_message}
        return self.master.call('messages/parse', _params)

    def send_raw(self, raw_message, from_email=None, from_name=None, to=None, async=False):
        """Take a raw MIME document for a message, and send it exactly as if it were sent over the SMTP protocol

        Args:
           raw_message (string): the full MIME document of an email message
           from_email (string|null): optionally define the sender address - otherwise we'll use the address found in the provided headers
           from_name (string|null): optionally define the sender alias
           to (array|null): optionally define the recipients to receive the message - otherwise we'll use the To, Cc, and Bcc headers provided in the document::
               to[] (string): the email address of the recipint
           async (boolean): enable a background sending mode that is optimized for bulk sending. In async mode, messages/sendRaw will immediately return a status of "queued" for every recipient. To handle rejections when sending in async mode, set up a webhook for the 'reject' event. Defaults to false for messages with no more than 10 recipients; messages with more than 10 recipients are always sent asynchronously, regardless of the value of async.

        Returns:
           array.  of structs for each recipient containing the key "email" with the email address and "status" as either "sent", "queued", or "rejected"::
               [] (struct): the sending results for a single recipient::
                   [].email (string): the email address of the recipient
                   [].status (string): the sending status of the recipient - either "sent", "queued", "rejected", or "invalid"
                   [].reject_reason (string): the reason for the rejection if the recipient status is "rejected"
                   []._id (string): the message's unique id


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'raw_message': raw_message, 'from_email': from_email, 'from_name': from_name, 'to': to, 'async': async}
        return self.master.call('messages/send-raw', _params)


class Whitelists(object):
    def __init__(self, master):
        self.master = master

    def add(self, email):
        """Adds an email to your email rejection whitelist. If the address is
currently on your blacklist, that blacklist entry will be removed
automatically.

        Args:
           email (string): an email address to add to the whitelist

        Returns:
           struct.  a status object containing the address and the result of the operation::
               email (string): the email address you provided
               whether (boolean): the operation succeeded

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email}
        return self.master.call('whitelists/add', _params)

    def list(self, email=None):
        """Retrieves your email rejection whitelist. You can provide an email
address or search prefix to limit the results. Returns up to 1000 results.

        Args:
           email (string): an optional email address or prefix to search by

        Returns:
           array.  up to 1000 whitelist entries::
               [] (struct): the information for each whitelist entry::
                   [].email (string): the email that is whitelisted
                   [].detail (string): a description of why the email was whitelisted
                   [].created_at (string): when the email was added to the whitelist


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email}
        return self.master.call('whitelists/list', _params)

    def delete(self, email):
        """Removes an email address from the whitelist.

        Args:
           email (string): the email address to remove from the whitelist

        Returns:
           struct.  a status object containing the address and whether the deletion succeeded::
               email (string): the email address that was removed from the blacklist
               deleted (boolean): whether the address was deleted successfully

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'email': email}
        return self.master.call('whitelists/delete', _params)


class Internal(object):
    def __init__(self, master):
        self.master = master


class Urls(object):
    def __init__(self, master):
        self.master = master

    def list(self, ):
        """Get the 100 most clicked URLs

        Returns:
           array.  the 100 most clicked URLs and their stats::
               [] (struct): the individual URL stats::
                   [].url (string): the URL to be tracked
                   [].sent (integer): the number of emails that contained the URL
                   [].clicks (integer): the number of times the URL has been clicked from a tracked email
                   [].unique_clicks (integer): the number of unique emails that have generated clicks for this URL


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('urls/list', _params)

    def search(self, q):
        """Return the 100 most clicked URLs that match the search query given

        Args:
           q (string): a search query

        Returns:
           array.  the 100 most clicked URLs matching the search query::
               [] (struct): the URL matching the query::
                   [].url (string): the URL to be tracked
                   [].sent (integer): the number of emails that contained the URL
                   [].clicks (integer): the number of times the URL has been clicked from a tracked email
                   [].unique_clicks (integer): the number of unique emails that have generated clicks for this URL


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'q': q}
        return self.master.call('urls/search', _params)

    def time_series(self, url):
        """Return the recent history (hourly stats for the last 30 days) for a url

        Args:
           url (string): an existing URL

        Returns:
           array.  the array of history information::
               [] (struct): the information for a single hour::
                   [].time (string): the hour as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the number of emails that were sent with the URL during the hour
                   [].clicks (integer): the number of times the URL was clicked during the hour
                   [].unique_clicks (integer): the number of unique clicks generated for emails sent with this URL during the hour


        Raises:
           UnknownUrlError: The requested URL has not been seen in a tracked link
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'url': url}
        return self.master.call('urls/time-series', _params)


class Webhooks(object):
    def __init__(self, master):
        self.master = master

    def list(self, ):
        """Get the list of all webhooks defined on the account

        Returns:
           array.  the webhooks associated with the account::
               [] (struct): the individual webhook info::
                   [].id (integer): a unique integer indentifier for the webhook
                   [].url (string): The URL that the event data will be posted to
                   [].description (string): a description of the webhook
                   [].auth_key (string): the key used to requests for this webhook
                   [].events (array): The message events that will be posted to the hook::
                       [].events[] (string): the individual message event (send, hard_bounce, soft_bounce, open, click, spam, unsub, or reject)

                   [].created_at (string): the date and time that the webhook was created as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].last_sent_at (string): the date and time that the webhook last successfully received events as a UTC string in YYYY-MM-DD HH:MM:SS format
                   [].batches_sent (integer): the number of event batches that have ever been sent to this webhook
                   [].events_sent (integer): the total number of events that have ever been sent to this webhook
                   [].last_error (string): if we've ever gotten an error trying to post to this webhook, the last error that we've seen


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('webhooks/list', _params)

    def add(self, url, description=None, events=[]):
        """Add a new webhook

        Args:
           url (string): the URL to POST batches of events
           description (string): an optional description of the webhook
           events (array): an optional list of events that will be posted to the webhook::
               events[] (string): the individual event to listen for

        Returns:
           struct.  the information saved about the new webhook::
               id (integer): a unique integer indentifier for the webhook
               url (string): The URL that the event data will be posted to
               description (string): a description of the webhook
               auth_key (string): the key used to requests for this webhook
               events (array): The message events that will be posted to the hook::
                   events[] (string): the individual message event (send, hard_bounce, soft_bounce, open, click, spam, unsub, or reject)

               created_at (string): the date and time that the webhook was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               last_sent_at (string): the date and time that the webhook last successfully received events as a UTC string in YYYY-MM-DD HH:MM:SS format
               batches_sent (integer): the number of event batches that have ever been sent to this webhook
               events_sent (integer): the total number of events that have ever been sent to this webhook
               last_error (string): if we've ever gotten an error trying to post to this webhook, the last error that we've seen

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'url': url, 'description': description, 'events': events}
        return self.master.call('webhooks/add', _params)

    def info(self, id):
        """Given the ID of an existing webhook, return the data about it

        Args:
           id (integer): the unique identifier of a webhook belonging to this account

        Returns:
           struct.  the information about the webhook::
               id (integer): a unique integer indentifier for the webhook
               url (string): The URL that the event data will be posted to
               description (string): a description of the webhook
               auth_key (string): the key used to requests for this webhook
               events (array): The message events that will be posted to the hook::
                   events[] (string): the individual message event (send, hard_bounce, soft_bounce, open, click, spam, unsub, or reject)

               created_at (string): the date and time that the webhook was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               last_sent_at (string): the date and time that the webhook last successfully received events as a UTC string in YYYY-MM-DD HH:MM:SS format
               batches_sent (integer): the number of event batches that have ever been sent to this webhook
               events_sent (integer): the total number of events that have ever been sent to this webhook
               last_error (string): if we've ever gotten an error trying to post to this webhook, the last error that we've seen

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           UnknownWebhookError: The requested webhook does not exist
           Error: A general Mandrill error has occurred
        """
        _params = {'id': id}
        return self.master.call('webhooks/info', _params)

    def update(self, id, url, description=None, events=[]):
        """Update an existing webhook

        Args:
           id (integer): the unique identifier of a webhook belonging to this account
           url (string): the URL to POST batches of events
           description (string): an optional description of the webhook
           events (array): an optional list of events that will be posted to the webhook::
               events[] (string): the individual event to listen for

        Returns:
           struct.  the information for the updated webhook::
               id (integer): a unique integer indentifier for the webhook
               url (string): The URL that the event data will be posted to
               description (string): a description of the webhook
               auth_key (string): the key used to requests for this webhook
               events (array): The message events that will be posted to the hook::
                   events[] (string): the individual message event (send, hard_bounce, soft_bounce, open, click, spam, unsub, or reject)

               created_at (string): the date and time that the webhook was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               last_sent_at (string): the date and time that the webhook last successfully received events as a UTC string in YYYY-MM-DD HH:MM:SS format
               batches_sent (integer): the number of event batches that have ever been sent to this webhook
               events_sent (integer): the total number of events that have ever been sent to this webhook
               last_error (string): if we've ever gotten an error trying to post to this webhook, the last error that we've seen

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           UnknownWebhookError: The requested webhook does not exist
           Error: A general Mandrill error has occurred
        """
        _params = {'id': id, 'url': url, 'description': description, 'events': events}
        return self.master.call('webhooks/update', _params)

    def delete(self, id):
        """Delete an existing webhook

        Args:
           id (integer): the unique identifier of a webhook belonging to this account

        Returns:
           struct.  the information for the deleted webhook::
               id (integer): a unique integer indentifier for the webhook
               url (string): The URL that the event data will be posted to
               description (string): a description of the webhook
               auth_key (string): the key used to requests for this webhook
               events (array): The message events that will be posted to the hook::
                   events[] (string): the individual message event (send, hard_bounce, soft_bounce, open, click, spam, unsub, or reject)

               created_at (string): the date and time that the webhook was created as a UTC string in YYYY-MM-DD HH:MM:SS format
               last_sent_at (string): the date and time that the webhook last successfully received events as a UTC string in YYYY-MM-DD HH:MM:SS format
               batches_sent (integer): the number of event batches that have ever been sent to this webhook
               events_sent (integer): the total number of events that have ever been sent to this webhook
               last_error (string): if we've ever gotten an error trying to post to this webhook, the last error that we've seen

        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           UnknownWebhookError: The requested webhook does not exist
           Error: A general Mandrill error has occurred
        """
        _params = {'id': id}
        return self.master.call('webhooks/delete', _params)


class Senders(object):
    def __init__(self, master):
        self.master = master

    def list(self, ):
        """Return the senders that have tried to use this account.

        Returns:
           array.  an array of sender data, one for each sending addresses used by the account::
               [] (struct): the information on each sending address in the account::
                   [].address (string): the sender's email address
                   [].created_at (string): the date and time that the sender was first seen by Mandrill as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the total number of messages sent by this sender
                   [].hard_bounces (integer): the total number of hard bounces by messages by this sender
                   [].soft_bounces (integer): the total number of soft bounces by messages by this sender
                   [].rejects (integer): the total number of rejected messages by this sender
                   [].complaints (integer): the total number of spam complaints received for messages by this sender
                   [].unsubs (integer): the total number of unsubscribe requests received for messages by this sender
                   [].opens (integer): the total number of times messages by this sender have been opened
                   [].clicks (integer): the total number of times tracked URLs in messages by this sender have been clicked


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('senders/list', _params)

    def domains(self, ):
        """Returns the sender domains that have been added to this account.

        Returns:
           array.  an array of sender domain data, one for each sending domain used by the account::
               [] (struct): the information on each sending domain for the account::
                   [].domain (string): the sender domain name
                   [].created_at (string): the date and time that the sending domain was first seen as a UTC string in YYYY-MM-DD HH:MM:SS format


        Raises:
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {}
        return self.master.call('senders/domains', _params)

    def info(self, address):
        """Return more detailed information about a single sender, including aggregates of recent stats

        Args:
           address (string): the email address of the sender

        Returns:
           struct.  the detailed information on the sender::
               address (string): the sender's email address
               created_at (string): the date and time that the sender was first seen by Mandrill as a UTC date string in YYYY-MM-DD HH:MM:SS format
               sent (integer): the total number of messages sent by this sender
               hard_bounces (integer): the total number of hard bounces by messages by this sender
               soft_bounces (integer): the total number of soft bounces by messages by this sender
               rejects (integer): the total number of rejected messages by this sender
               complaints (integer): the total number of spam complaints received for messages by this sender
               unsubs (integer): the total number of unsubscribe requests received for messages by this sender
               opens (integer): the total number of times messages by this sender have been opened
               clicks (integer): the total number of times tracked URLs in messages by this sender have been clicked
               stats (struct): an aggregate summary of the sender's sending stats::
                   stats.today (struct): stats for this sender so far today::
                       stats.today.sent (integer): the number of emails sent for this sender so far today
                       stats.today.hard_bounces (integer): the number of emails hard bounced for this sender so far today
                       stats.today.soft_bounces (integer): the number of emails soft bounced for this sender so far today
                       stats.today.rejects (integer): the number of emails rejected for sending this sender so far today
                       stats.today.complaints (integer): the number of spam complaints for this sender so far today
                       stats.today.unsubs (integer): the number of unsubscribes for this sender so far today
                       stats.today.opens (integer): the number of times emails have been opened for this sender so far today
                       stats.today.unique_opens (integer): the number of unique opens for emails sent for this sender so far today
                       stats.today.clicks (integer): the number of URLs that have been clicked for this sender so far today
                       stats.today.unique_clicks (integer): the number of unique clicks for emails sent for this sender so far today

                   stats.last_7_days (struct): stats for this sender in the last 7 days::
                       stats.last_7_days.sent (integer): the number of emails sent for this sender in the last 7 days
                       stats.last_7_days.hard_bounces (integer): the number of emails hard bounced for this sender in the last 7 days
                       stats.last_7_days.soft_bounces (integer): the number of emails soft bounced for this sender in the last 7 days
                       stats.last_7_days.rejects (integer): the number of emails rejected for sending this sender in the last 7 days
                       stats.last_7_days.complaints (integer): the number of spam complaints for this sender in the last 7 days
                       stats.last_7_days.unsubs (integer): the number of unsubscribes for this sender in the last 7 days
                       stats.last_7_days.opens (integer): the number of times emails have been opened for this sender in the last 7 days
                       stats.last_7_days.unique_opens (integer): the number of unique opens for emails sent for this sender in the last 7 days
                       stats.last_7_days.clicks (integer): the number of URLs that have been clicked for this sender in the last 7 days
                       stats.last_7_days.unique_clicks (integer): the number of unique clicks for emails sent for this sender in the last 7 days

                   stats.last_30_days (struct): stats for this sender in the last 30 days::
                       stats.last_30_days.sent (integer): the number of emails sent for this sender in the last 30 days
                       stats.last_30_days.hard_bounces (integer): the number of emails hard bounced for this sender in the last 30 days
                       stats.last_30_days.soft_bounces (integer): the number of emails soft bounced for this sender in the last 30 days
                       stats.last_30_days.rejects (integer): the number of emails rejected for sending this sender in the last 30 days
                       stats.last_30_days.complaints (integer): the number of spam complaints for this sender in the last 30 days
                       stats.last_30_days.unsubs (integer): the number of unsubscribes for this sender in the last 30 days
                       stats.last_30_days.opens (integer): the number of times emails have been opened for this sender in the last 30 days
                       stats.last_30_days.unique_opens (integer): the number of unique opens for emails sent for this sender in the last 30 days
                       stats.last_30_days.clicks (integer): the number of URLs that have been clicked for this sender in the last 30 days
                       stats.last_30_days.unique_clicks (integer): the number of unique clicks for emails sent for this sender in the last 30 days

                   stats.last_60_days (struct): stats for this sender in the last 60 days::
                       stats.last_60_days.sent (integer): the number of emails sent for this sender in the last 60 days
                       stats.last_60_days.hard_bounces (integer): the number of emails hard bounced for this sender in the last 60 days
                       stats.last_60_days.soft_bounces (integer): the number of emails soft bounced for this sender in the last 60 days
                       stats.last_60_days.rejects (integer): the number of emails rejected for sending this sender in the last 60 days
                       stats.last_60_days.complaints (integer): the number of spam complaints for this sender in the last 60 days
                       stats.last_60_days.unsubs (integer): the number of unsubscribes for this sender in the last 60 days
                       stats.last_60_days.opens (integer): the number of times emails have been opened for this sender in the last 60 days
                       stats.last_60_days.unique_opens (integer): the number of unique opens for emails sent for this sender in the last 60 days
                       stats.last_60_days.clicks (integer): the number of URLs that have been clicked for this sender in the last 60 days
                       stats.last_60_days.unique_clicks (integer): the number of unique clicks for emails sent for this sender in the last 60 days

                   stats.last_90_days (struct): stats for this sender in the last 90 days::
                       stats.last_90_days.sent (integer): the number of emails sent for this sender in the last 90 days
                       stats.last_90_days.hard_bounces (integer): the number of emails hard bounced for this sender in the last 90 days
                       stats.last_90_days.soft_bounces (integer): the number of emails soft bounced for this sender in the last 90 days
                       stats.last_90_days.rejects (integer): the number of emails rejected for sending this sender in the last 90 days
                       stats.last_90_days.complaints (integer): the number of spam complaints for this sender in the last 90 days
                       stats.last_90_days.unsubs (integer): the number of unsubscribes for this sender in the last 90 days
                       stats.last_90_days.opens (integer): the number of times emails have been opened for this sender in the last 90 days
                       stats.last_90_days.unique_opens (integer): the number of unique opens for emails sent for this sender in the last 90 days
                       stats.last_90_days.clicks (integer): the number of URLs that have been clicked for this sender in the last 90 days
                       stats.last_90_days.unique_clicks (integer): the number of unique clicks for emails sent for this sender in the last 90 days



        Raises:
           UnknownSenderError: The requested sender does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'address': address}
        return self.master.call('senders/info', _params)

    def time_series(self, address):
        """Return the recent history (hourly stats for the last 30 days) for a sender

        Args:
           address (string): the email address of the sender

        Returns:
           array.  the array of history information::
               [] (struct): the stats for a single hour::
                   [].time (string): the hour as a UTC date string in YYYY-MM-DD HH:MM:SS format
                   [].sent (integer): the number of emails that were sent during the hour
                   [].hard_bounces (integer): the number of emails that hard bounced during the hour
                   [].soft_bounces (integer): the number of emails that soft bounced during the hour
                   [].rejects (integer): the number of emails that were rejected during the hour
                   [].complaints (integer): the number of spam complaints received during the hour
                   [].opens (integer): the number of emails opened during the hour
                   [].unique_opens (integer): the number of unique opens generated by messages sent during the hour
                   [].clicks (integer): the number of tracked URLs clicked during the hour
                   [].unique_clicks (integer): the number of unique clicks generated by messages sent during the hour


        Raises:
           UnknownSenderError: The requested sender does not exist
           InvalidKeyError: The provided API key is not a valid Mandrill API key
           Error: A general Mandrill error has occurred
        """
        _params = {'address': address}
        return self.master.call('senders/time-series', _params)



