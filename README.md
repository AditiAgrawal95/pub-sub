# pub-sub
1)	Open Ubuntu based instances on Amazon EC2, either via ssh or clicking the Connect button.
 
Select an instance to run.
Connect by clicking on the Connect button, and a new tab with the instance will open.
Run the ssh command on the terminal to connect to the instance via the command line terminal, or Similarly, open the other instances on Amazon EC2.
Make Sure you have selected the security group.

2)	Copy the py files to respective instances via Winscp. Fill in the Public IPv4 DNS address as the hostname, username - ubuntu, and in Advanced->Authentication-> Upload the ppk file ( the public key file generated while creating the instance). 
Click on Tools->Preferences-> Uncheck Transfer resuming.
 
3)	Setup python and flask in each of the Ubuntu based EC2 instances:
Command: sudo apt update; sudo apt install pip3; sudo pip3 install Flask

4)	Bring up the zookeeper.
Command: sudo python3 zookeeper.py <Port_no_of_zookeper_terminal> < Ip_of_Leader_Node>:<Port_of_leader>
Example: sudo python3 zookeeper.py 1000 172.31.24.174:2000
5)	Bring up Leader Node
Command: sudo python3 node.py <Ip_of_Leader> <ip_zookeper>:<Port_of_Zookeeper> 
Example: sudo python3 node.py 2000 172.31.28.203:1000 
6)	Bring up Publisher
Command: sudo python3 publisher.py <Port_of_publisher> <Name_of_Publisher>  <IP_of_Zookeeper>:<Port_of_Zookeeper>
Example: sudo python3 publisher.py 3000 P1 172.31.28.203:1000
7)	Bring up Subscriber
Command: sudo python3 subscriber.py <Port_of_subscriber> <ip_zookeper>:<Port_of_Zookeeper>
Example: sudo python3 subscriber.py 4000 172.31.28.203:1000
8)	Subscribe to Publisher
In a python shell run:
Command: requests.post('http://<IP_of_Subscriber>:<Port_of_Subscriber>/new_subscription', json={'publisher_name':<Publisher_Name>})
Example: requests.post('http://172.31.28.203:4000/new_subscription', json={'publisher_name':'P1'})
9)	Publish message
Command: requests.post('http://<IP_of_Publisher>:<Port_of_Publisher>/new_msg', json={'pub_id':'P1', 'data':'Message 1 from Pub1'})
Example: requests.post('http://172.31.28.203:3000/new_msg', json={'pub_id':'P1', 'data':'Message 1 from Pub1'})

Scenarios:
1)	Basic Pub-Sub
○	Bring up zookeeper
○	Bring up Leader
○	Bring up pub1
○	Bring up sub1
○	Subscribe sub1 to pub1
○	Send data from pub1 to Leader
○	Check data received at sub1
2)	New subscription to the new publisher
○	Bring up pub 2
○	Subscribe sub1 to pub 2
○	Send data from pub2 to Leader
○	Check if sub1 received data.
○	Check the replicated data’s message if the ‘subTopub’ list is updated.
3)	Scalability by distributing subscribers.
○	Bring up Worker node 1
○	Check if the leader has printed the statement “ Balance of…..”
○	Check the ‘nodeTosub’ key in the replicated data’s message, has all the subscribers mapped to the respective nodes. One each for each node.
4)	Replication of data
○	Send new data from either pub1 or pub2.
○	Or Add a new subscriber, or publisher.
○	Check on the worker node, the replicated message structure should contain, the newly added subscriber in ‘subToPub’ or newly added publisher in ‘pubToSub’ or new data in ‘messageQ’ .
5)	Leader Election 
○	Bring up worker Node 3
○	Add sub3
○	Subscribe sub3 to pub1 and pub2
○	Send data from pub1 and pub2
○	Bring Leader down now
○	Check in both the worker node, where the detection has taken place and the leader election has started, by looking for "Leader election started"
○	Check “New leader elected: <ip_address_new_leader>” on all worker nodes.
○	Check the subscribers have been added to other worker nodes, and check for “Balancing done after a worker died”
○	Send data from pub1 to Leader
○	Check on the worker node the replicated message structure. Check for ‘nodeTosub’ which should have the new list of subscribers attached to nodes.
○	Check if all the subscribers have received the data.
6)	Fault Tolerance
○	Bring a worker Node down.
○	Check for “Balancing done after a worker died” on Leader.
○	Add a sub to the worker node, and send data from a pub.
○	Check in the replicated message structure ‘nodeTosub’ list, which should have the new list of node-to-subscriber mapping.
