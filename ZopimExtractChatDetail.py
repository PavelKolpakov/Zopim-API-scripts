import requests
import json
from itertools import zip_longest
import pandas as pd
import numpy as np
from datetime import datetime
from datetime import timedelta
from time import sleep

config = {
  'username': 'You Zopim Login',
  'password': 'Your Zopim Password (better use API token)',
  'base_path': 'https://www.zopim.com/api/v2'
}

date_entry = input('Enter a date in YYYY-MM-DD format\n')
year, month, day = map(int, date_entry.split('-'))
user_date = datetime(year, month, day)

length = int (input('How many days you want to have in Report?\n'))-1

user_date1 = user_date+timedelta(days=1)


#Since we are hitting the same subdomain with same endpoints lets take care of headers and auth just one time and reuse
s = requests.Session()
s.auth = (config['username'], config['password'])
s.headers.update({"content-type":"application/json"})

#This is a little helper funciton that will take x of something, and let you chunk through a subset
#Note that 'n' is the chunk size
def _grouper(n, iterable, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(fillvalue=fillvalue, *args)

#Since you want a report by month, lets just create a function to get all the chat IDs for a two digit month and 4 digit year

def get_chat_ids_for_period(user_date, user_date1, length):
 all_chat_ids = []
 my_list = []
 i=0
 while i < length+1:
   search_query = "timestamp:[{0} TO {1}]".format((user_date+timedelta(days=i)).strftime('%Y-%m-%dT00:00'), (user_date1+timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%S'))
   print(search_query)
   params = {"q":search_query}
   url = "{0}/chats/search".format(config['base_path'])
   while url:
     r = s.get(url, params=params)
     print(url)
     if r.status_code == 200:
       response = json.loads(r.text)
       print(r.status_code)
       for chat in response['results']:
         all_chat_ids.append(chat['id'])
         url = response['next_url']

     else:

       if r.status_code == 429:
          sleep(3)
          print("sweet time of sleep")
       else:
         print("A request failed in the loop")

         get_chat_ids_for_period(user_date, datetime.strptime(chat['timestamp'], '%Y-%m-%dT%H:%M:%SZ'), length) #str()
         print(r)
         break
   my_list.append (all_chat_ids)
   i=i+1
# my_listn = ''.join(str(my_list) )
# print(my_listn)
 print(chat['timestamp'])
 return all_chat_ids #my_listn

def build_csv_data(queried_id_list):
  all_chats_for_csv = []
  for chunk in _grouper(50, queried_id_list):
    filtered = [id for id in chunk if id is not None] #Only needed for last set of 50 that will have some sort of remainder filled with 'None' values by the grouper() function
    url = "{0}/chats".format(config['base_path'])
    stringified_ids = ",".join(filtered)
    params = {"ids":stringified_ids}
    r = s.get(url, params=params)
    if r.status_code == 200:
      response = json.loads(r.text)
      docs = response['docs']
      for k in docs:
        doc_obj = docs[k] #This is the 'doc' object. Note that some keys may not exist for all items. Duration does not exist for offline messages for example
        all_chats_for_csv.append(doc_obj)
    else:
        if r.status_code == 429:
          sleep(4)
        else:
          print("error getting bulk chats")
  return all_chats_for_csv

#grab the ids for the specified range NOTE!! This is where you can change the year/month for the date range.
queried_id_list = get_chat_ids_for_period(user_date , user_date1, length)

#turn those into raw objects
csv_obj_data = build_csv_data(queried_id_list)

#create a list to hold our rows
all_rows_as_obj = []
#turn the raw objects into nice and tasty ones that pandas can digest
for record in csv_obj_data:
  try:
    response_time = record.get('response_time', {})
    count = record.get('count',{})
    csv_obj = {
      "email": record['visitor']['email'],
      "agent": ",".join(record.get('agent_names', "N/A")),
      "visitor": record['visitor']['name'],
      "department": record['department_name'],
      "url": record.get('webpath', "N/A"),
      "missed": record.get('missed', "N/A"),
      "resp_first": response_time.get('first', []),
      "resp_max": response_time.get('max', []),
      "resp_avg": response_time.get('avg', []),
      "start timestamp": record['session']['start_date'],
      "end timestamp": record['session']['end_date'],
      "total messages": count.get('total', 0),
      "Agent Msg Count": count.get('agent', 0),
      "Visitor Msg Count": count.get('visitor', 0),
      "rating": record.get('rating',[]),
      "ticket_id": record['zendesk_ticket_id'],
      "history": record.get('history', "N/A")
    }
  except KeyError as e:
    print(e)
    print("key error occured for record with id: {}".format(record['id']))
    print(record)
    pass
  all_rows_as_obj.append(csv_obj)

#with prettier objects our column names can just come from a call to the first object's keys
col_keys = all_rows_as_obj[0].keys()

#create the dataframe, list comprehension creates an array of rows based on the column names we got
#Let pandas do the hard part with csvs
csv_frame = pd.DataFrame([[i[j] for j in col_keys] for i in all_rows_as_obj], columns=col_keys)

#coerce ticket_id to be int not float
csv_frame['ticket_id'] = csv_frame['ticket_id'].fillna(0).astype(np.int64)

#fill blank values with the string 'N/A'
csv_frame = csv_frame.fillna("N/A")

#output to a file
csv_frame.to_csv( (user_date).strftime('%Y-%m-%d') + ' TO ' + (user_date+timedelta(days=(length))).strftime('%Y-%m-%d') + '.csv')