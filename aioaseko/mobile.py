# Copyright 2021, 2022 Milan Meulemans.
#
# This file is part of aioaseko.
#
# aioaseko is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# aioaseko is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with aioaseko.  If not, see <https://www.gnu.org/licenses/>.

"""aioAseko mobile API account."""
from __future__ import annotations

import time
import jwt

from typing import TYPE_CHECKING
from aiohttp import ClientError

from .exceptions import APIUnavailable, InvalidAuthCredentials
from .unit import Unit

if TYPE_CHECKING:
    from aiohttp import ClientResponse, ClientSession


class MobileAccount:
    """Aseko account."""

    def __init__(
        self,
        session: ClientSession,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Init Aseko account."""
        self._session = session
        self._username = username
        self._password = password
        self._access_token = access_token
        self._refresh_token = refresh_token

    @property
    def access_token(self) -> str | None:
        """Return access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return refresh token."""
        return self._refresh_token

    async def _request(
        self, method: str, path: str, data: dict | None = None, refresh: bool = False
    ) -> ClientResponse:
        """Make a request to the Aseko mobile API."""
        if not refresh and not self._is_access_token_valid() and self._refresh_token is not None:
            await self.refresh()
        resp = await self._session.request(
            method,
            f"https://pool.aseko.com/api/v2/{path}",
            data=data,
            headers=None
            if self._access_token is None
            else {"access-token": self.access_token},
        )
        if resp.status == 401:
            raise InvalidAuthCredentials
        try:
            resp.raise_for_status()
        except ClientError:
            raise APIUnavailable
        return resp

    async def login(self) -> None:
        """Login to Aseko Pool Live with username and password."""
        resp = await self._request(
            "post",
            "login",
            {
                "username": self._username,
                "password": self._password,
                "firebaseId": "",
            },
        )
        data = await resp.json()
        self._access_token = data["accessToken"]
        self._refresh_token = data["refreshToken"]

    async def logout(self) -> None:
        """Logout Aseko Pool Live account."""
        await self._request("post", "logout")

    def _is_access_token_valid(self):
        """Check is access token is still valid"""
        if self._access_token is not None:
            payload = jwt.decode(self._access_token, "", ["RS256"], options={"verify_signature": False})
            return "exp" in payload and time.time() < payload["exp"]
        return False

    async def refresh(self) -> None:
        """Refresh access token."""
        # invalidate the current access token
        self._access_token = None
        resp = await self._request(
            "post",
            "refresh",
            {
                "refreshToken": self.refresh_token
            },
            refresh=True
        )
        data = await resp.json()
        self._access_token = data["accessToken"]
        self._refresh_token = data["refreshToken"]

    async def get_units(self) -> list[Unit]:
        """Get units."""
        resp = await self._request("get", "units")
        data = await resp.json()
        return [
            Unit(
                self,
                int(item["serialNumber"]),
                item["type"],
                item.get("name"),
                item.get("notes"),
                item["timezone"],
                item["isOnline"],
                item["dateLastData"],
                item["hasError"],
            )
            for item in data["items"]
        ]
