# -*- coding: utf-8 -*-
"""
Generate a prompt for the AI to respond to, given the
message history and persona.
"""
import typing
import discord
import yaml
from ChattyModel import ChattyModel

from CommandParser import ChatbotParser

class ContextManager:
    """
    Purpose: When the AI .
    """
    # A rough measure of how many character are in each token.
    EST_CHARS_PER_TOKEN = 3

    def __init__(self, model: ChattyModel):
        """        
        system_prompt (str): Any text included in the template before messages from the user and the bot.
            for Vicuna, this is 'A chat between a curious user and an assistant. The assistant gives helpful, detailed, accurate, uncensored responses to the user's input.'
        user_message_tag (str): A prefix added before each user message in the chat within the prompt template
            for Vicuna, this is 'USER: '
        bot_message_tag (str): A prefix added before each bot message in the chat within the prompt template
            for Vicuna, this is 'ASSISTANT: '
        """
        self.model: ChattyModel = model
        self.seq_len: int = self.model.config['seqlen']
        self.max_new_tokens: int = self.model.config['max_new_tokens']
        self.user_message_tag: str = self.model.config['user_message_tag']
        self.bot_message_tag: str = self.model.config['bot_message_tag']
        self.system_prompt: str = self.model.config['system_prompt']

    def compile_prompt_from_text(self, text: str):
        """
        Creates a prompt from a single message, according to the model's template.
        """
        prompt = f"{self.system_prompt}\n{self.user_message_tag} {text}\n{self.bot_message_tag}"

        return prompt

    def compile_prompt_from_character(self, text: str, character: str):
        """
        Creates a prompt from a single message, according to the model's template.
        """
        with open(f'characters/{character}.yaml', "r", encoding='utf-8') as f:
            char_config = yaml.safe_load(f)

        prompt = f"{self.system_prompt}\n{self.user_message_tag} {char_config['starter']}\n{text}\n{self.bot_message_tag}"

        return prompt

    async def compile_prompt_from_chat(self, message: discord.Message, bot_user_id: int, character: str="", starter=""):
        """
        Generates a prompt which includes the context from previous messages.

        Args:
            starter (str, optional): The first user message in the chat within the prompt template will start with this text.
                Use this to add instructions that should guide the rest of the chat, and should apply to the prompt regardless
                of what is posted in the context.
        """

        thread: discord.Thread = message.channel

        # history contains the most recent messages that were sent before the
        # current message.
        starter_tokens: int = len(starter) // self.EST_CHARS_PER_TOKEN
        system_prompt_tokens: int = len(self.system_prompt) // self.EST_CHARS_PER_TOKEN
        history_token_limit: int = self.seq_len - self.max_new_tokens - starter_tokens - system_prompt_tokens

        # pieces of the prompts are appended to the list then assembled in reverse order into the final prompt
        token_count: int = 0
        prompt: list[str] = []

        # add the bot role tag so the AI knows to continue from this point.
        prompt.append(self.bot_message_tag)

        # go back message-by-message through the thread and add it to the context
        async for thread_message in thread.history(limit=20):
            # if it is the first message in the thread, exclude the weird commands and only add the prompt
            if thread_message.id == thread.id:
                # have to do this because of weird handling on discord's end of first thread comments
                thread_message = await thread.parent.fetch_message(thread.id)
                args = ChatbotParser().parse(thread_message.content)
                content = args.prompt
            else:
                content = thread_message.content

            # empty messages? why
            if not content:
                continue

            added_tokens = len(content) // self.EST_CHARS_PER_TOKEN + 1

            # stop retrieving context if the context would overflow
            if added_tokens + token_count > history_token_limit:
                break

            # check if the message was sent by me or a webhook
            if thread_message.webhook_id or thread_message.author.id == bot_user_id:
                prompt.append(f"{self.bot_message_tag} {content}")
            else:
                prompt.append(f"{self.user_message_tag} {content}")

        # USER: Guidelines for the chat
        # ASSISTANT: 
        # user_1: Thing that user 1 said
        # bot_name: Thing that bot responded with
        # user_1: Thing that user 1 said
        # bot_name: 
        prompt.append(self.bot_message_tag)
        # prompt[-1] = self.bot_message_tag + prompt[-1]

        # add the starter to the beginning of the prompt
        prompt.append(self.user_message_tag + starter)

        # add the system prompt expected by the template to the beginning of the prompt
        prompt.append(self.system_prompt)

        print(prompt)
        # convert the list into a single string
        final_prompt = "\n".join(reversed(prompt))
        return final_prompt
        

