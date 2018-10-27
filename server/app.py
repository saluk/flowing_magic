from flask import Flask, jsonify, request, redirect, url_for, abort
from flask_login import current_user, login_user
from flask_security import Security, login_required, \
     SQLAlchemySessionUserDatastore
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import json
import sys

# Create app
app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'super-secret'
app.config['SECURITY_PASSWORD_SALT'] = '@$^%&SFHK5327fxzn'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///server.db'

# Setup Flask-Security
db = SQLAlchemy(app)

from conndb import init_db, Base
from models import User, Role, Game
sys.path.append("..")
import flowmodel

user_datastore = SQLAlchemySessionUserDatastore(db.session,
                                                User, Role)
Base.query = db.session.query_property()
security = Security(app, user_datastore)

# Create a user to test with
@app.before_first_request
def create_user():
    init_db()
    try:
        user_datastore.create_user(nickname="bob",email='bob@bob.com', password='password')
        user_datastore.create_user(nickname="sara",email='sara@sara.com', password='password')
        db.session.commit()
    except:
        db.session.rollback()

@app.route('/register', methods=["GET","POST"])
def register():
    def return_form(nickname_error="",email_error="",password_error=""):
        register_html = """<form method="post" action="/register"><br>
        Public Nickname [5-15 chars]:<input name="nickname" /><br><p style="color:red">%s</p><br>
        Private login email address:<input name="email" /><p style="color:red">%s</p><br>
        Password:<input type="password" name="password" /><p style="color:red">%s</p><br>
        <input type="submit"></form><br>"""
        return register_html%(nickname_error,email_error,password_error)
    if request.method == 'POST':
        nickname_error=email_error=password_error=""
        if request.json:
            email,nickname,password = request.json["email"],request.json["nickname"],request.json["password"]
        else:
            email,nickname,password = request.form["email"],request.form["nickname"],request.form["password"]
        if len(email)<10 or "." not in email[-4:] or not "@" in email[:-4] or email.count("@")>1:
            email_error = "Invalid email"
        if len(password)<8 or len(password)>255:
            password_error = "Password must be between 8 and 20 characters long"
        if len(nickname)<5 and len(nickname)<15:
            nickname_error = "Nickname must be between 5 and 15 characters long"
        if email_error or password_error or nickname_error:
            return return_form(nickname_error,email_error,password_error)
        user = user_datastore.create_user(email=email, password=password, nickname=nickname)
        db.session.commit()
        print("Created user",user)
        login_user(user)
        return redirect(url_for("home"))
    return return_form()

def game_info(game):
    info = {"id":str(game.id)}
    users = []
    for user in game.users:
        users.append({"nickname":user.nickname,"user_id":user.id})
    info["users"]=users
    return info

@app.route('/loginclient', methods=["POST"])
def login_from_client():
    print(request.json)
    user = db.session.query(User).filter_by(email=request.json["email"]).first()
    if not user:
        abort(404)
    games = [game_info(g) for g in sorted(user.games,key=lambda g:g.updated) if g.status!="closed"]
    waiting_games = db.session.query(Game).filter_by(status="open")
    waiting_games = [game_info(g) for g in sorted(waiting_games,key=lambda g:g.updated or datetime.now()) if user not in g.users]
    login_user(user)
    print("client logged in")
    return jsonify({"user_id":user.id,"nickname":user.nickname,"games":games,"waiting_games":waiting_games})

@app.route('/newgame')
@login_required
def newgame():
    if [g for g in current_user.games if g.status=="open"]:
        abort(404)
    g = Game(updated=datetime.now(),status="open")
    game = flowmodel.newgame()
    game.state["players"][str(current_user.id)] = {"user_id":str(current_user.id),"player_key":random.choice(["player1","player2"])}
    g.state = json.dumps(game.state)
    g.users.append(current_user)
    db.session.add(g)
    db.session.commit()
    return redirect(url_for("get_game_state",game_id=g.id,last_time=-1))

@app.route('/game/<int:game_id>/<last_time>')
@login_required
def get_game_state(game_id,last_time):
    print("GETTING GAME STATE")
    game = db.session.query(Game).filter_by(id=game_id).first()
    if current_user not in game.users:
        print("USER NOT IN GAME")
        return jsonify({"error":"user is not in game"})
    if game.status=="closed":
        return jsonify({"error":"game_closed"})
    state = json.loads(game.state)
    if state["time"]<=int(last_time):
        return jsonify({"error":"stale_state"})
    flowstate = flowmodel.from_state(state)
    print("RETURNING GAME")
    return jsonify({"game_id":game_id,"user_id":str(current_user.id),"state":flowstate.state})

@app.route('/join/<int:game_id>')
@login_required
def join(game_id):
    game = db.session.query(Game).filter_by(id=game_id).first()
    if current_user in game.users:
        return jsonify({"error":"already there"})
    if game.status!="open":
        return jsonify({"error":"game is full"})
    if len(game.users)>=2:
        return jsonify({"error":"game is full - but we shouldn't get here"})
    state = json.loads(game.state)

    players = ["player1","player2"]
    existing = list(state["players"].values())[0]["player_key"]
    players.remove(existing)
    state["players"][str(current_user.id)] = {"user_id":str(current_user.id),"player_key":players[0]}

    game.status = "active"
    game.state = json.dumps(state)
    game.users.append(current_user)
    db.session.add(game)
    db.session.commit()
    return redirect(url_for("get_game_state",game_id=game.id,last_time=-1))

@app.route('/concede/<int:game_id>')
@login_required
def concede(game_id):
    game = db.session.query(Game).filter_by(id=game_id).first()
    if game.status=="closed":
        abort(301)
    if current_user not in game.users:
        abort(301)
    game.status = "closed"
    db.session.add(game)
    db.session.commit()
    return jsonify({"action":"success"})

#TODO make card_id a string in the model
@app.route('/action/<string:action>/<int:game_id>/<int:card_id>/<string:space_id>')
@login_required
def action(action,game_id,card_id,space_id):
    game = db.session.query(Game).filter_by(id=game_id).first()
    if current_user not in game.users:
        return jsonify({"error":"user is not in game"})
    state = json.loads(game.state)
    m = flowmodel.GameModel(state)
    player = None
    if m.state["players"][str(current_user.id)]["player_key"] != m.state["current_player"]:
        return jsonify({"error":"it's not your turn"})
    try:
        m.get_object(card_id).action(action,m.get_object(space_id))
    except flowmodel.ModelError as exc:
        return jsonify({"error":"invalid manipulation","message":exc.args,"type":str(type(exc))})
    m.world.end_turn()
    game.state = json.dumps(m.state)
    game.updated = datetime.now()
    db.session.add(game)
    db.session.commit()
    return redirect(url_for("get_game_state",game_id=game.id,last_time=-1))

# Views
@app.route('/')
@login_required
def home():
    d = {
        "user":current_user.nickname,
        "email":current_user.email,
        "id":current_user.id,
        #"password":current_user.password,
        }
    if current_user.games:
        d["games"] = ["/game/%s"%(g.id,) for g in current_user.games]
    return jsonify(d)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(somewhere)

if __name__ == '__main__':
    app.run()
