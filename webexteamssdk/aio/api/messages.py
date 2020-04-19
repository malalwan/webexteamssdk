# -*- coding: utf-8 -*-
"""Webex Teams Messages API wrapper.

Copyright (c) 2016-2019 Cisco and/or its affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import aiohttp

from webexteamssdk.models.cards import AdaptiveCard
from webexteamssdk.aio.generator_containers import async_generator_container

from webexteamssdk.aio.restsession import AsyncRestSession
from webexteamssdk.aio.utils import (
    check_type,
    dict_from_items_with_values,
    is_local_file,
    is_web_url,
    make_attachment,
    open_local_file,
)


API_ENDPOINT = "messages"
OBJECT_TYPE = "message"


class AsyncMessagesAPI:
    """Webex Teams Messages API.

    Wraps the Webex Teams Messages API and exposes the API as native Python
    methods that return native Python objects.

    """

    def __init__(self, session: AsyncRestSession, object_factory):
        """Init a new MessagesAPI object with the provided RestSession.

        Args:
            session(RestSession): The RESTful session object to be used for
                API calls to the Webex Teams service.

        Raises:
            TypeError: If the parameter types are incorrect.

        """
        check_type(session, AsyncRestSession)
        super().__init__()
        self._session = session
        self._object_factory = object_factory

    @async_generator_container
    async def list(
        self,
        roomId,
        mentionedPeople=None,
        before=None,
        beforeMessage=None,
        max=None,
        **request_parameters,
    ):
        """Lists messages in a room.

        Each message will include content attachments if present.

        The list API sorts the messages in descending order by creation date.

        This method supports Webex Teams's implementation of RFC5988 Web
        Linking to provide pagination support.  It returns a generator
        container that incrementally yields all messages returned by the
        query.  The generator will automatically request additional 'pages' of
        responses from Webex as needed until all responses have been returned.
        The container makes the generator safe for reuse.  A new API call will
        be made, using the same parameters that were specified when the
        generator was created, every time a new iterator is requested from the
        container.

        Args:
            roomId(str): List messages for a room, by ID.
            mentionedPeople(str): List messages where the caller is
                mentioned by specifying "me" or the caller `personId`.
            before(str): List messages sent before a date and time, in
                ISO8601 format.
            beforeMessage(str): List messages sent before a message,
                by ID.
            max(int): Limit the maximum number of items returned from the Webex
                Teams service per request.
            **request_parameters: Additional request parameters (provides
                support for parameters that may be added in the future).

        Returns:
            GeneratorContainer: A GeneratorContainer which, when iterated,
            yields the messages returned by the Webex Teams query.

        Raises:
            TypeError: If the parameter types are incorrect.
            ApiError: If the Webex Teams cloud returns an error.

        """
        check_type(roomId, str)
        check_type(mentionedPeople, str, optional=True)
        check_type(before, str, optional=True)
        check_type(beforeMessage, str, optional=True)
        check_type(max, int, optional=True)

        params = dict_from_items_with_values(
            request_parameters,
            roomId=roomId,
            mentionedPeople=mentionedPeople,
            before=before,
            beforeMessage=beforeMessage,
            max=max,
        )

        # API request - get items
        items = await self._session.get_items(API_ENDPOINT, params=params)

        # Yield message objects created from the returned items JSON objects
        for item in items:
            yield self._object_factory(OBJECT_TYPE, item)

    async def create(
        self,
        roomId=None,
        toPersonId=None,
        toPersonEmail=None,
        text=None,
        markdown=None,
        files=None,
        attachments=None,
        **request_parameters,
    ):
        """Post a message to a room.

        The files parameter is a list, which accepts multiple values to allow
        for future expansion, but currently only one file may be included with
        the message.

        Args:
            roomId(str): The room ID.
            toPersonId(str): The ID of the recipient when sending a
                private 1:1 message.
            toPersonEmail(str): The email address of the recipient when
                sending a private 1:1 message.
            text(str): The message, in plain text. If `markdown` is
                specified this parameter may be optionally used to provide
                alternate text for UI clients that do not support rich text.
            markdown(str): The message, in markdown format.
            files(list): A list of public URL(s) or local path(s) to files to
                be posted into the room. Only one file is allowed per message.
            attachments(list): Content attachments to attach to the message.
                See the Cards Guide for more information.
            **request_parameters: Additional request parameters (provides
                support for parameters that may be added in the future).

        Returns:
            Message: A Message object with the details of the created message.

        Raises:
            TypeError: If the parameter types are incorrect.
            ApiError: If the Webex Teams cloud returns an error.
            ValueError: If the files parameter is a list of length > 1, or if
                the string in the list (the only element in the list) does not
                contain a valid URL or path to a local file.

        """
        check_type(roomId, str, optional=True)
        check_type(toPersonId, str, optional=True)
        check_type(toPersonEmail, str, optional=True)
        check_type(text, str, optional=True)
        check_type(markdown, str, optional=True)
        check_type(files, list, optional=True)
        check_type(attachments, list, optional=True)

        if files:
            if len(files) > 1:
                raise ValueError(
                    "The `files` parameter should be a list with "
                    "exactly one (1) item. The files parameter "
                    "is a list, which accepts multiple values to "
                    "allow for future expansion, but currently "
                    "only one file may be included with the "
                    "message."
                )
            check_type(files[0], str)
        else:
            files = None

        # Process and serialize attachments
        if attachments:
            for item, attachment in enumerate(attachments):
                check_type(attachment, (dict, AdaptiveCard))

                if isinstance(attachments, AdaptiveCard):
                    attachments[item] = make_attachment(attachment)

        post_data = dict_from_items_with_values(
            request_parameters,
            roomId=roomId,
            toPersonId=toPersonId,
            toPersonEmail=toPersonEmail,
            text=text,
            markdown=markdown,
            files=files,
            attachments=attachments,
        )

        # API request
        if not files or is_web_url(files[0]):
            # Standard JSON post
            json_data = await self._session.post(API_ENDPOINT, json=post_data)

        elif is_local_file(files[0]):
            # Multipart MIME post
            try:
                post_data.pop("files", None)
                post_data.pop("attachements", None)
                file = open_local_file(files[0])
                with aiohttp.MultipartWriter() as mpwriter:
                    payload = mpwriter.append(file.file_object)
                    payload.headers[
                        "Content-Disposition"
                    ] = f'form-data; name="files"; filename="{file.file_name}"'
                    for k, v in post_data.items():
                        payload = mpwriter.append(v)
                        payload.headers[
                            "Content-Disposition"
                        ] = f'form-data; name="{k}"'

                json_data = await self._session.post(
                    API_ENDPOINT,
                    headers={
                        "Content-type": f"multipart/form-data; boundary={mpwriter.boundary}"
                    },
                    data=mpwriter,
                )
            finally:
                if not file.file_object.closed:
                    file.file_object.close()
        else:
            raise ValueError(
                "The `files` parameter does not contain a vaild "
                "URL or path to a local file."
            )

        # Return a message object created from the response JSON data
        return self._object_factory(OBJECT_TYPE, json_data)

    async def get(self, messageId):
        """Get the details of a message, by ID.

        Args:
            messageId(str): The ID of the message to be retrieved.

        Returns:
            Message: A Message object with the details of the requested
            message.

        Raises:
            TypeError: If the parameter types are incorrect.
            ApiError: If the Webex Teams cloud returns an error.

        """
        check_type(messageId, str)

        # API request
        json_data = await self._session.get(API_ENDPOINT + "/" + messageId)

        # Return a message object created from the response JSON data
        return self._object_factory(OBJECT_TYPE, json_data)

    async def delete(self, messageId):
        """Delete a message.

        Args:
            messageId(str): The ID of the message to be deleted.

        Raises:
            TypeError: If the parameter types are incorrect.
            ApiError: If the Webex Teams cloud returns an error.

        """
        check_type(messageId, str)

        # API request
        await self._session.delete(API_ENDPOINT + "/" + messageId)
