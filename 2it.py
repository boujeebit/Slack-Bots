import os, requests
import time
import json
from slackclient import SlackClient


# starterbot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

# constants
AT_BOT = "<@" + BOT_ID + ">"
REC_COMMAND = "recommend"
HLP_COMMAND = "help"
RANDOM_COMMAND = "random"
SERVER_PATH = "http://sms.nullify.online:8000"
DEV = True

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

if DEV:
    SERVER_PATH = "http://10.3.17.200:8000"

def handle_command(command, channel, user):

    command = command.split(' ')

    if command[0] == REC_COMMAND:

        #Get who to send it to
        send_to = get_user_from_string(command)

        #Pop the recommend
        command.pop(0)

        #Populate recommendation until we get yo user
        recommendation = ''
        for word in command:
            if word != 'to' and word[0] != '<':
                recommendation += " " + word
            else:
                break

        response = "%s, %s has made a recommendation: %s" % (get_user_name(send_to), get_user_name(user.upper()), recommendation)
        recommend(user.upper(), send_to, recommendation)
        slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)

    elif command[0] == HLP_COMMAND:
        response = "Welcome to the 2it bot. Here are sample commands to get started.\n  @2it recommend Mr. Robot to @adam\n  @2it recommend Harry Potter and the Sorcerer's Stone to @Ryan"
        slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)

    elif command[0] == RANDOM_COMMAND:
        rec = get_random_recommendation(user.upper())
        print rec
        if not "errors" in rec:
            post_recommendation_to_chat(rec, channel)
        else:
            slack_client.api_call("chat.postMessage", channel=channel, text=rec['errors']['message'], as_user=True)

    else: 
        response = "I didn't understand that. Use the 'help' command to learn more."
        slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)

def parse_slack_output(slack_rtm_output):

    output_list = slack_rtm_output

    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip(), \
                       output['channel'], \
                       output['user']

    return None, None, None

# Creates a new recommendation where source is recommending concept to the target.
def recommend(source, target, concept):
    print "recommending.."
    api_request = SERVER_PATH + "/api/recommendations"

    data = {
        "recommendation" : {
            "concept" : concept,
            "source" : get_person(source)['id'],
            "target" : get_person(target)['id'],
            "message" : "",
        }
    }

    r = requests.post(api_request, json=data)
    print r.text

# Gets a person object based on a slack_id from our api.
def get_person(slack_id):
    print "Getting person: " + slack_id

    slack_profile = get_profile(slack_id)

    api_request = SERVER_PATH + "/api/persons"
    data = {
        "person" : {
            "slack" : slack_id,
            "email" : slack_profile['email'],
            "name" : slack_profile['real_name_normalized']
        }
    }

    res = requests.post(api_request, json=data)
    print res.text
    return json.loads(res.text)['person']

# Gets a random recommendation for target=slack_id.
def get_random_recommendation(slack_id):
    print "Getting random recommendation for slack_id=" + slack_id
    api_request = SERVER_PATH + "/api/recommendations?slack=" + slack_id
    res = requests.get(api_request)
    return json.loads(res.text)
    
# Posts a single recommendation to the slack channel.
def post_recommendation_to_chat(rec, channel):
    concept = rec['concept']
    recommendations = rec['recommendations']
    people = rec['persons']

    plaintext = "You should get around to checking out " + concept['name']

    link = concept['url']

    attachments = [
        {
            "fallback": plaintext,
            "color": "#36a64f",
            "pretext": plaintext,
            "title": concept['title'],
            "title_link": concept['url'],
            "image_url": concept['image'],
            "footer": "Wikipedia",
            "footer_icon": "https://en.wikipedia.org/static/favicon/wikipedia.ico",
        }
    ]

    recommenders = []
    for r in recommendations:
        print r
        source = (person for person in people if person['id'] == r['source']).next()
        recommenders.append(source['name'])
        
    recommenders_msg =  "Recommended by: " + ", ".join(recommenders)

    attachments.append({
            "fallback" : recommenders_msg,
            "text" : recommenders_msg,
        })
    slack_client.api_call("chat.postMessage", channel=channel, attachments=attachments, as_user=True)


# Returns the slack profile object for the userid.
def get_profile(userid):
    key =os.environ.get('USER_KEY')
    api_request = "https://slack.com/api/users.profile.get?token=%s&user=%s&pretty=1" % (key, userid,)

    r = requests.get(api_request)
    return json.loads(r.text)['profile']

# Gets the user name for userid.
def get_user_name(userid):
    return get_profile(userid)['real_name_normalized']

def get_user_from_string(command):
    for word in command:
        if word[0] == '<':
            userid = word

    userid = userid[2:-1]

    if userid == 'U25LWNMFH':
        return None

    return userid


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel and user:
                handle_command(command, channel, user)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
