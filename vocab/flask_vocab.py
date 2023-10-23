"""
Flask web site with vocabulary matching game
(identify vocabulary words that can be made
from a scrambled string)
"""

import flask
from flask import request, session

import logging

# Our modules
from src.letterbag import LetterBag
from src.vocab import Vocab
from src.jumble import jumbled
import src.config as config


###
# Globals
###
app = flask.Flask(__name__)

CONFIG = config.configuration()
app.secret_key = CONFIG.SECRET_KEY  # Should allow using session variables

#
# One shared 'Vocab' object, read-only after initialization,
# shared by all threads and instances.  Otherwise we would have to
# store it in the browser and transmit it on each request/response cycle,
# or else read it from the file on each request/responce cycle,
# neither of which would be suitable for responding keystroke by keystroke.

WORDS = Vocab(CONFIG.VOCAB)
SEED = CONFIG.SEED
try:
    SEED = int(SEED)
except ValueError:
    SEED = None


###
# Pages
###

@app.route("/")
@app.route("/index")
def index():
    """The main page of the application"""
    flask.g.vocab = WORDS.as_list()
    flask.session["target_count"] = min(
        len(flask.g.vocab), CONFIG.SUCCESS_AT_COUNT)
    flask.session["jumble"] = jumbled(
        flask.g.vocab, flask.session["target_count"], seed=None if not SEED or SEED < 0 else SEED)
    flask.session["matches"] = []
    app.logger.debug("Session variables have been set")
    assert flask.session["matches"] == []
    assert flask.session["target_count"] > 0
    app.logger.debug("At least one seems to be set correctly")
    return flask.render_template('vocab.html')


@app.route("/keep_going")
def keep_going():
    """
    After initial use of index, we keep the same scrambled
    word and try to get more matches
    """
    flask.g.vocab = WORDS.as_list()
    return flask.render_template('vocab.html')


@app.route("/success")
def success():
    return flask.render_template('success.html')


#######################
# Form handler.
#   You'll need to change this to a
#   a JSON request handler
#######################

@app.route("/_check", methods=["POST", "GET"])
def check():
    """
    User has submitted the form with a word ('attempt')
    that should be formed from the jumble and on the
    vocabulary list.  We respond depending on whether
    the word is on the vocab list (therefore correctly spelled),
    made only from the jumble letters, and not a word they
    already found.
    """
    app.logger.debug("Entering check")

    try:
        result = {}
    # The data we need, from form and from cookie
        text = request.args.get("text")
        jumble = flask.session["jumble"]
        matches = flask.session.get("matches", [])
    # Is it good?
        in_jumble = LetterBag(jumble).contains(text)
        matched = WORDS.has(text)
    # Respond appropriately
        if matched and in_jumble and not (text in matches):
        # Cool, they found a new word
            matches.append(text)
            result["matches"] = matches
        elif text in matches:
            result["message"] = "You already found {}".format(text)
        elif not matched:
            result["message"] = "{} isn't in the list of words".format(text)
        elif not in_jumble:
            result["message"] = '"{}" can\'t be made from the letters {}'.format(text, jumble)
        else:
            app.logger.debug("This case shouldn't happen!")
            assert False  # Raises AssertionError

    # Choose page:  Solved enough, or keep going?
        if len(matches) >= flask.session["target_count"]:
            result["redirect"] = flask.url_for("success")
        else:
            result["redirect"] = flask.url_for("keep_going")

        app.logger.debug("redirect is {}".format(result["redirect"]))
        app.logger.debug("matches is {}".format(result["matches"]))
        return flask.jsonify(result=result)

    except Exception as e:
        return flask.jsonify(error=str(e))
###############
# AJAX request handlers
#   These return JSON, rather than rendering pages.
###############

@app.route("/_example")
def example():
    """
    Example ajax request handler
    """
    app.logger.debug("Got a JSON request")
    rslt = {"key": "value"}
    return flask.jsonify(result=rslt)

@app.route("/_check/word", methods=["POST"])
def check_word():
    
    # Grab data from the AJAX request
    text = flask.request.form["attempt"]
    jumble = flask.session["jumble"]
    matches = flask.session.get("matches", [])

    # Checking if word is a match to a word in letterbag
    in_jumble = LetterBag(jumble).contains(text)
    matched = WORDS.has(text)

    # Prepare the response data
    response = {
            "valid_word": matched and in_jumble,
            "already_found": text in matches,
    }

    # Update found words if the word is valid
    if response["valid_word"] and not response["already_found"]:
        matches.append(text)
        flask.session["matches"] = matches
    
    # Choose page: Success or keep going
    if len(matches) >= flask.session["target_count"]:
        response["redirect_url"] = flask.url_for("success")

    return flask.jsonify(result=response)

#################
# Functions used within the templates
#################

@app.template_filter('filt')
def format_filt(something):
    """
    Example of a filter that can be used within
    the Jinja2 code
    """
    return "Not what you asked for"

###################
#   Error handlers
###################


@app.errorhandler(404)
def error_404(e):
    app.logger.warning("++ 404 error: {}".format(e))
    return flask.render_template('404.html'), 404


@app.errorhandler(500)
def error_500(e):
    app.logger.warning("++ 500 error: {}".format(e))
    assert not True  # I want to invoke the debugger
    return flask.render_template('500.html'), 500


@app.errorhandler(403)
def error_403(e):
    app.logger.warning("++ 403 error: {}".format(e))
    return flask.render_template('403.html'), 403


#############

if __name__ == "__main__":
    if CONFIG.DEBUG:
        app.debug = True
        app.logger.setLevel(logging.DEBUG)
        app.logger.info(
            "Opening for global access on port {}".format(CONFIG.PORT))
    app.run(port=CONFIG.PORT, host="0.0.0.0", debug=CONFIG.DEBUG)
