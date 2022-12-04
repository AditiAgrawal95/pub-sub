from flask import Flask, request, jsonify                 
import threading
import json
import requests
import sys

host_name = "0.0.0.0"
flask_port = 3000
id = 'P0'
app = Flask(__name__)

leader_url = '0.0.0.0:2000'
zookeeper_url = '0.0.0.0:1000'

@app.route("/", methods=['GET'])
def home():
  return "Home"

# for dev to call
@app.route("/new_msg", methods=['POST'])
def new_msg():
  msg = json.loads(request.data)
  message = msg['data']
  obj = { 'pub_id':id, 'message': message}
  call_zookeeper()
  response = requests.post('http://' + leader_url + '/post_new_message', json=obj)
  return response.json()

def register_with_leader():
  requests.post('http://' + leader_url + '/register', json={'id':id})

def call_zookeeper():
  global mode_leader, leader_url
  response = requests.get('http://' + zookeeper_url + '/leader')
  r = response.json()
  leader_url = r['leader']


if __name__ == "__main__":
  if len(sys.argv) > 1:
    flask_port = sys.argv[1] # eg. 3000
    id = sys.argv[2] # eg. P1
    if len(sys.argv) > 3:
      zookeeper_url = sys.argv[3]

  call_zookeeper()
  
  threading.Thread(target=lambda: 
                   app.run(host=host_name, port=flask_port, debug=True, use_reloader=False, threaded=True)).start()

  with app.app_context():
    register_with_leader()

