from flask import Flask, request, jsonify                 
import threading
import json
import requests
import array as arr
import sys
import socket
import time
import math

host_name = "0.0.0.0"
flask_port = 2000
app = Flask(__name__)
q_pub_msg_id = [0] * 10 #Queue to store publisher, message, and message-id
msg_counter = -1
subscriber_to_publisher = {}
publisher_to_subscriber = {}
nodes_to_subscriber = {}
worker_id = "0.0.0.0" + str(flask_port)
msg_cnt_self = 0
mode_leader = False
zookeeper_url = "0.0.0.0:1000"
leader_url = ''
msg_send_cnt = 0  ## Counter for leader
msg_replicate_cnt = 0 ## Counter for worker node
HEARTBEAT_TIMER = 8 # Todo: Reduce this to 5?
REPLICATION_TIMER = 10
LEADER_ELECTION_TIMER = 15
POLLING_DURATION = 5
alive_nodes = {}
is_leader_election_triggered = False

@app.route("/", methods=['GET'])
def home():
  return "Home"

@app.route("/register", methods=['POST'])
def register():
  msg = json.loads(request.data)
  id = msg['id']
  publisher_to_subscriber[id] = []
  print("New publisher registered: " + str(id))
  response = {"status":"Success"}
  return jsonify(response)

@app.route("/alive", methods=['POST'])
def alive():
  msg = json.loads(request.data)
  print(msg)
  id = msg['worker_id']
  if not id in nodes_to_subscriber:
    nodes_to_subscriber[id] = []
    balance_subscriber_count_new_node(id)
    response = {"messageQ" : q_pub_msg_id, 
         "leaderMsgCounter": msg_counter,
         "subToPub": subscriber_to_publisher,
         "pubToSub": publisher_to_subscriber, 
         "nodeToSub": nodes_to_subscriber}
    print("New node added: " + str(id))
  else:
    response = {"status":"Success"}
  alive_nodes[id] = True
  return jsonify(response)

def heartbeat_send():
  global mode_leader, leader_url, q_pub_msg_id, msg_counter, subscriber_to_publisher, publisher_to_subscriber, nodes_to_subscriber, msg_send_cnt, msg_replicate_cnt, msg_cnt_self
  
  while(True):
    if not mode_leader:
      try:
        response = requests.post('http://' + leader_url + '/alive',
                                 json={"worker_id": worker_id})
        
        res = response.json()
        if not 'status' in res:
          q_pub_msg_id = res['messageQ']
          msg_counter = res['leaderMsgCounter'] 
          subscriber_to_publisher = res['subToPub']
          publisher_to_subscriber = res['pubToSub']
          nodes_to_subscriber = res['nodeToSub']
          msg_send_cnt = msg_counter ## Counter for leader
          msg_replicate_cnt = msg_counter + 1 ## Counter for worker node
          msg_cnt_self = msg_counter + 1
          print("Data synced with leader")
      except requests.ConnectionError as e:
        print("Connection error when sending heartbeat to leader")
        if not is_leader_election_triggered:
          leader_election()      
        
    time.sleep(HEARTBEAT_TIMER)

# coordinator
def leader_election():
  global is_leader_election_triggered
  print("Leader election started")
  is_leader_election_triggered = True #set some flag as True?
  available_nodes = list(nodes_to_subscriber.keys())
  available_nodes.remove(leader_url)
  other_worker_nodes = list(available_nodes)
  if worker_id in other_worker_nodes:
    other_worker_nodes.remove(worker_id)
  attributes = {}
  for node in other_worker_nodes:
    try:
      response = requests.get('http://' + node + '/leader_election_triggered')
      r = response.json()
      attributes[node] = r['attribute']
    except Exception as e:
      # leader was dead, and a worker also died
      print('Exception in leader_election func for node:' + node)

  new_leader_url = worker_id
  new_attribute = msg_counter
  for node, attribute in attributes.items():
    if attribute > new_attribute or (attribute == new_attribute and node > new_leader_url):
      new_leader_url = node
      new_attribute = attribute
  
  available_nodes.remove(new_leader_url)
  available_nodes.insert(0, new_leader_url) # inform the leader first    
  for node in available_nodes:
    response = requests.post('http://' + node + '/leader_elected', json={'leader_url': new_leader_url})

@app.route("/leader_election_triggered", methods=['GET'])
def leader_election_triggered():
  print("Leader election has already been started")
  global is_leader_election_triggered
  is_leader_election_triggered = True
  threading.Thread(target=listen_for_elected_leader).start()
  response = {"attribute" : msg_counter}
  return jsonify(response)

def listen_for_elected_leader():
  count = 0
  while(count < LEADER_ELECTION_TIMER/POLLING_DURATION):
    if not is_leader_election_triggered:
      break
    count = count + 1
    time.sleep(POLLING_DURATION)

  if is_leader_election_triggered:
    print("Leeader election timed out, lets re trigger election")
    leader_election()

@app.route("/leader_elected", methods=['POST'])
def leader_elected():
  msg = json.loads(request.data)
  new_leader_url = msg["leader_url"]
  print('New leader elected: '+ str(new_leader_url))
  new_leader_setup(new_leader_url) 
  response = {"status":"success"}
  return jsonify(response)

def new_leader_setup(new_leader_url):
  global is_leader_election_triggered, leader_url, mode_leader
  old_leader = leader_url
  leader_url = new_leader_url
  if leader_url == worker_id:
    mode_leader = True
    balance_subscriber_count(old_leader)
    obj = { "new_leader_url" : leader_url}
    requests.post('http://' + zookeeper_url + '/update_leader', json=obj)
  is_leader_election_triggered = False
  
def heartbeat_check():
  while(True):
    if mode_leader:
      for node in list(alive_nodes):
        is_alive = alive_nodes[node]
        if is_alive:
          alive_nodes[node] = False # reset it and wait for /alive to set it again
        else:
          # rebalance
          print("Worker node has died: " + str(node))
          balance_subscriber_count(node)
          alive_nodes.pop(node)
      
    time.sleep(HEARTBEAT_TIMER)
    
def call_zookeeper():
  global mode_leader, leader_url
  print("Zookeper url: " + zookeeper_url)
  response = requests.get('http://' + zookeeper_url + '/leader')
  r = response.json()
  leader_url = r['leader']
  if worker_id == leader_url:
    print("I am leader")
    mode_leader = True

def balance_subscriber_count(deleted_node):
  
  list_of_extra_subs = nodes_to_subscriber[deleted_node]
  nodes_to_subscriber.pop(deleted_node)
  list_of_available_nodes = list(nodes_to_subscriber.keys())
  
  i = 0
  while i < len(list_of_extra_subs):
    for node in list_of_available_nodes:
      if i < len(list_of_extra_subs):
        nodes_to_subscriber[node].append(list_of_extra_subs[i])
      i = i + 1

  print("Balancing done after worker died")
  print(nodes_to_subscriber)

def balance_subscriber_count_new_node(new_node):
  global nodes_to_subscriber
  subscriber_sum = 0
  node_count = 0 
  min_subscriber_count = 0
  for n,s in nodes_to_subscriber.items():
    subscriber_sum = subscriber_sum + len(s)
    
  node_count = len(nodes_to_subscriber)
  
  if node_count > 0:
    min_subscriber_count = math.floor(subscriber_sum / node_count)
    
  list_of_available_nodes = list(nodes_to_subscriber.keys())
  list_of_available_nodes.remove(new_node)

  while len(nodes_to_subscriber[new_node]) < min_subscriber_count:
    for node in list_of_available_nodes:
      if len(nodes_to_subscriber[node]) > min_subscriber_count:
        nodes_to_subscriber[new_node].append(nodes_to_subscriber[node].pop())

  print("Balancing done when new node is added")
  print(nodes_to_subscriber)
  
  
  
# Listen to new content from the publisher.
@app.route("/post_new_message", methods=['POST'])
def post_new_message():
  global msg_counter
  # when the node goes down, re-register the publisher
  msg = json.loads(request.data)
  print(msg)
  # check if the data is read correctly. Add the code later.
  pub_id = msg["pub_id"]
  pub_msg = msg["message"]
  print("New message from publisher " + str(pub_id) + ": " + str(pub_msg))
  msg_counter = msg_counter + 1
  list_entry = [pub_id,pub_msg,msg_counter]
  q_pub_msg_id[msg_counter%10] = list_entry
  print(q_pub_msg_id)
  
  response = {"status":"success"}
  return jsonify(response)

'''Brief: Function is called when the replicate Thread starts.
          It runs a while loop which calls replicate_data_to_WorkerNodes 
          function if it is a leader node. '''
def call_replicate_data():
  global mode_leader
  
  while(True):
    if mode_leader == True:
      time.sleep(REPLICATION_TIMER)
      replicate_data_to_workerNodes()

'''Brief:  Function is called by call_replicate_data.
           It sends the incremental data to other worker nodes.
           Sends: the dictionaries, leader's message counter and
           the changed message Queue to the worker nodes'''
def replicate_data_to_workerNodes():
  global msg_send_cnt
  list_of_worker_nodes = list(nodes_to_subscriber.keys())
  list_of_worker_nodes.remove(worker_id)
  if len(list_of_worker_nodes) > 0:
    new_data_in_Q = []  # construct a smaller Q that contains changed/new data
    while(msg_send_cnt <= msg_counter):
      new_data_in_Q.append(q_pub_msg_id[msg_send_cnt%10])
      msg_send_cnt = msg_send_cnt + 1
    for worker_node in list_of_worker_nodes:
      print("Sending replicated data to: " + worker_node)
      obj = { "subToPub" : subscriber_to_publisher, "pubToSub" : publisher_to_subscriber, "nodeToSub" : nodes_to_subscriber , "messageQ" : new_data_in_Q, "leaderMsgCounter" : msg_counter}
  
      try:
        requests.post('http://' + worker_node + '/receive_replicated_data', json=obj)
      except requests.ConnectionError as e:
        print("ConnectionError for: " + worker_node)
        print(e) 


'''Brief: Function is an endpoint at worker Node, accessed by the Leader 
          It updates the dictionaries and updates the message Queue with 
          the changed data'''
@app.route("/receive_replicated_data", methods = ['POST'])
def receive_replicated_data():
  global msg_replicate_cnt, msg_counter
  global subscriber_to_publisher, publisher_to_subscriber, nodes_to_subscriber, q_pub_msg_id
  
  msg = json.loads(request.data)
  print("inside receive_replicated_data")
  print(msg)
  
  ## Update database
  subscriber_to_publisher = msg['subToPub']
  publisher_to_subscriber = msg['pubToSub']
  nodes_to_subscriber = msg['nodeToSub']
  new_data_inQ = msg['messageQ']
  leader_msg_counter = msg['leaderMsgCounter']
  cnt_new_data_inQ = 0
  
  ## Update the message data Queue.
  while(msg_replicate_cnt <= leader_msg_counter):
    q_pub_msg_id[msg_replicate_cnt % 10] = new_data_inQ[cnt_new_data_inQ]
    msg_counter = msg_counter + 1
    cnt_new_data_inQ = cnt_new_data_inQ + 1
    msg_replicate_cnt = msg_replicate_cnt + 1 

  print(q_pub_msg_id)
  response = {"status":"success"}
  return jsonify(response)

  
'''Brief: Function is called when the send data Thread starts.
          It runs a while loop which calls broadcast_to_subscriber 
          function. '''
def call_send_data():
  while(True):
    broadcast_to_subscriber()

'''Brief: Function is called by call_send_data.
          '''
# Worker is sending to the respective subscribers  
def broadcast_to_subscriber():
  global msg_cnt_self, worker_id
  if not worker_id in nodes_to_subscriber:
    return
  list_of_subscribers = nodes_to_subscriber[worker_id]
  
  while(msg_cnt_self <= msg_counter):
    print("Broadcasting data to: " + str(list_of_subscribers))
    list_subs_for_each_pub = publisher_to_subscriber[q_pub_msg_id[msg_cnt_self%10][0]]
    for subId in list_subs_for_each_pub:
      if (subId in list_of_subscribers):
        obj = { 'message': q_pub_msg_id[msg_cnt_self%10][1], 'msgid' : q_pub_msg_id[msg_cnt_self%10][2]}
        requests.post('http://' + subId + '/send_to_subscriber', json=obj)
    msg_cnt_self = msg_cnt_self + 1
 
@app.route("/subscribe", methods=['POST'])
def subscribe_to_publisher():
  msg = json.loads(request.data)
  subscriber_id = msg["subscriber_id"]
  publisher_name = msg["publisher_name"]

  if not publisher_name in publisher_to_subscriber:
    response = {"status":"Publisher not available anymore"}
    return response
  
  if subscriber_id in subscriber_to_publisher:
    if not publisher_name in subscriber_to_publisher[subscriber_id]:
      subscriber_to_publisher[subscriber_id].append(publisher_name)
  else:
    subscriber_to_publisher[subscriber_id] = [publisher_name]
    # add subscriber to a specific node's load
    min_worker_id = worker_id
    for k,v in nodes_to_subscriber.items():
      if(len(v) < len(nodes_to_subscriber[min_worker_id])):
        min_worker_id = k
    nodes_to_subscriber[min_worker_id].append(subscriber_id)

  if not subscriber_id in publisher_to_subscriber[publisher_name]:
    publisher_to_subscriber[publisher_name].append(subscriber_id)
    
  print(subscriber_to_publisher)
  print(publisher_to_subscriber)
  print(nodes_to_subscriber)
   
  response = {"status":"success"}
  return jsonify(response)
  

if __name__ == "__main__":

  if len(sys.argv) > 1:
    flask_port = sys.argv[1] # eg. 2000
    zookeeper_url = sys.argv[2]  # 172.10.15.201

  host_name = socket.gethostname()
  host_ip = socket.gethostbyname(host_name)
  worker_id = host_ip + ":" + str(flask_port)
  call_zookeeper()

  if(mode_leader):
    nodes_to_subscriber[worker_id] = []
  
  threading.Thread(target=lambda: 
                   app.run(host=host_name, port=flask_port, debug=True, use_reloader=False, threaded=True)).start()

  ## Thread to send data to subscribers
  threading.Thread(target=call_send_data).start()
  ## Thread to replicate data to worker nodes
  threading.Thread(target=call_replicate_data).start()
  threading.Thread(target=heartbeat_send).start()
  threading.Thread(target=heartbeat_check).start() # for leader only


