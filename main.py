import telegram
from telegram.ext import Updater, CommandHandler,MessageHandler,CallbackContext
from telegram.ext import messagequeue as mq
from telegram.ext import Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,Update

import audiotools
import logging
import os
import threading
import traceback
import time

from config import Config

config=Config()

TELEGRAM_TOKEN=config.telegram_api_token

logger = logging.getLogger(__name__)

# utils
def get_chat_id(update):
  chat_id = None
  if update.message is not None:
    chat_id = update.message.chat.id
  elif update.channel_post is not None:
    chat_id = update.channel_post.chat.id
  return chat_id

def get_message_id(update):
  if update.message is not None:
    return update.message.message_id
  elif update.channel_post is not None:
    return update.channel_post.message_id
  return None

def get_message_user_firstname(update):
    return update.message.from_user.first_name



class Transcriber(threading.Thread):
  def __init__(self, threadID,bot,update,path):
    threading.Thread.__init__(self)
    self.threadID=threadID
    self.bot=bot
    self.update=update
    self.path=path

  def run(self):
    path=self.path
    lang="en"
    chat_id=get_chat_id(self.update)
    message_id=get_message_id(self.update)
    is_group=chat_id <0

    print("Started Processing. ID: "+str(message_id))

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Stop", callback_data=message_id)]])
    message = self.bot.send_message(
                        chat_id=chat_id, 
                        text="Transcribing..\n",
                        reply_to_message_id=message_id,
                        parse_mode="html",
                        is_group=is_group
                      )
    text ="<b>Text:</b>" + "\n"
    success = False

    for speech in audiotools.transcribe(path,lang):
      retry = True
      retry_num = 0

      while retry:
        try:
          if len(text + speech) >= 4080:
            text = "<b>[continues]:</b>" + "\n"
            message = self.bot.send_message(
              chat_id=chat_id,
              text=text + speech + " <b>[..]</b>",
              reply_to_message_id=message.message_id,
              parse_mode="html",
              is_group=is_group,
              reply_markup=keyboard
            )
          else:
            message = self.bot.edit_message_text(
                text=text + speech + " <b>[..]</b>", 
                chat_id=chat_id, 
                message_id=message.message_id,
                parse_mode="html",
                is_group=is_group,
                reply_markup=keyboard
                )

          text += ' ' + speech
          retry = False
          success = True

        except telegram.error.TimedOut as t:
          logger.error("Timeout error %s", traceback.format_exc())
          retry_num += 1
          if retry_num >= 3:
            retry = False
        
        except telegram.error.RetryAfter as r:
          logger.warning("Retrying after %d", r.retry_after)
          time.sleep(r.retry_after)

        except telegram.error.TelegramError as te:
          logger.error("Telegram error %s", traceback.format_exc())
          retry = False

        except Exception as e:
          logger.error("Exception %s", traceback.format_exc())
          retry = False

    retry = True
    retry_num = 0
    while retry:
      try:
        if success:
          self.bot.edit_message_text(
            text=text, 
            chat_id=chat_id, 
            message_id=message.message_id,
            parse_mode="html",
            is_group=is_group
          )
        else:
          self.bot.edit_message_text("Could not transcribe audio\n",
            chat_id=chat_id,
            message_id=message.message_id,
            parse_mode="html",
            is_group=is_group
          )
        retry = False
      except telegram.error.TimedOut as t:
        logger.error("Timeout error %s", traceback.format_exc())
        retry_num += 1
        if retry_num >= 3:
          retry = False
      
      except telegram.error.RetryAfter as r:
        logger.warning("Retrying after %d", r.retry_after)
        time.sleep(r.retry_after)

      except telegram.error.TelegramError as te:
        logger.error("Telegram error %s", traceback.format_exc())
        retry = False

      except Exception as e:
        logger.error("Exception %s", traceback.format_exc())
        retry = False 
      finally:
        if os.path.exists(path):
          os.remove(path)
        print("Completed. ID: "+str(message_id))


      
def transcribe_audio_file(bot, update, path):
  chat_id = get_chat_id(update)
  message_id = get_message_id(update)

  logger.debug("Starting thread %d", message_id)
  t=Transcriber(message_id,bot,update,path)
  t.start()


def process_media_voice(bot, update, media, name):
  chat_id = get_chat_id(update)
  file_size = media.file_size
  message_id = get_message_id(update)

  if file_size >= 20*(1024**2):
    
    bot.send_message(
      chat_id=chat_id, 
      text="Sorry, file is too big! (20MB limit)\n",
      reply_to_message_id=message_id,
      parse_mode="html",
      is_group=chat_id < 0
    )
    return

  
  if not os.path.exists("temp"):
    os.mkdir("temp")

  file_id = media.file_id
  file_path = os.path.join("temp", file_id)
  file = bot.get_file(file_id)  
  file.download(file_path)

  try:
    print("Ready for transcribing. ID: "+str(message_id))
    transcribe_audio_file(bot, update, file_path)
    
  except Exception as e:
    logger.error("Exception handling %s from %d: %s", name, chat_id, traceback.format_exc())
  finally:
    pass
    


# Message callbacks
def private_message(bot, update):
  chat_id = get_chat_id(update)
  bot.send_message(
    chat_id=chat_id, 
    text=R.get_string_resource("message_private", TBDB.get_chat_lang(chat_id))
  )



def new_chat_member(bot, update):
  message = update.message or update.channel_post

  if bot.get_me() in message.new_chat_members:
    welcome_message(bot, update)


def audio(update:Update,context:CallbackContext):
  bot=context.bot
  chat_id = get_chat_id(update)
  message = update.message or update.channel_post
  a= message.audio
  print("Audio File Received")
  process_media_voice(bot,update,a,"audio")


def voice(update:Update,context:CallbackContext):
  bot=context.bot
  chat_id = get_chat_id(update)
  message = update.message or update.channel_post
  v = message.voice
  print("New voice Received")
  process_media_voice(bot,update,v,"voice")

def hello(update, context):
    update.message.reply_text(
        'Hello {}'.format(get_message_user_firstname(update)))



if __name__ == "__main__":
    print("Bot Started.")
    while True:
      try:
        updater = Updater(TELEGRAM_TOKEN,use_context=True)
        updater.dispatcher.add_handler(MessageHandler(Filters.voice,voice))
        updater.dispatcher.add_handler(MessageHandler(Filters.audio,audio))
        updater.start_polling()
        updater.idle()
      except:
        logger.error("Exception handling in Main %s", traceback.format_exc())
        print("Something went wrong. Waiting for 2 seconds.")
        time.sleep(2)



