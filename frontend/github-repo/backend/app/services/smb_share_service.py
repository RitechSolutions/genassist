import asyncio
import fnmatch
import os
import shutil
from pathlib import Path
from typing import List, Optional, Union

import aiofiles

# High-level convenience layer that ships with smbprotocol
# Installed via `pip install smbprotocol`
from smbclient import (
    register_session,
    reset_connection_cache,
    open_file,
    scandir,
    mkdir,
    rmdir,
    remove,
    path as smbpath,
    stat as smbstat,
    SMBDirEntry,
)


class SMBShareFSService:
    """
    Async-enabled, injectable service to manage file operations either on:
      - Local filesystem (Linux/Windows), or
      - SMB shares via smbprotocol's smbclient (NO OS mount required)

    Supports context management:
        async with SMBShareFSService(...) as svc:
            await svc.list_dir(...)

    Public API mirrors the original service (list_dir, read_file, write_file, etc.)
    """

    def __init__(
        self,
        smb_host: Optional[str] = None,
        smb_share: Optional[str] = None,
        smb_user: Optional[str] = None,
        smb_pass: Optional[str] = None,
        smb_port: Optional[int] = None,  # optional, defaults handled by library
        use_local_fs: bool = False,
        local_root: Optional[Union[str, Path]] = None,
    ):
        """
        Args:
            smb_host/smb_share/smb_user/smb_pass: SMB connection settings (ignored in local mode)
            smb_port: Optional explicit SMB port (e.g., 445)
            use_local_fs: True to operate on local filesystem
            local_root: Base path for local operations (defaults to current working dir)
        """
        self.use_local_fs = use_local_fs

        # Local base (equivalent to previous self.smb_mount semantic)
        self.local_root = Path(local_root or os.getenv("LOCAL_ROOT", "."))

        # SMB settings
        if not use_local_fs:
            self.smb_host = smb_host or os.getenv("SMB_HOST")
            self.smb_share = smb_share or os.getenv("SMB_SHARE")
            self.smb_user = smb_user or os.getenv("SMB_USER")
            self.smb_pass = smb_pass or os.getenv("SMB_PASS")
            self.smb_port = smb_port or (int(os.getenv("SMB_PORT")) if os.getenv("SMB_PORT") else None)

            if not all([self.smb_host, self.smb_share]):
                raise ValueError("Missing SMB environment variables (SMB_HOST, SMB_SHARE).")

        # Session state (SMB)
        self._session_registered = False

    # --------------------------------------------------------------------------
    # Context management (register/unregister SMB session)
    # --------------------------------------------------------------------------
    async def __aenter__(self):
        if not self.use_local_fs:
            # smbclient keeps an internal connection cache.
            # Register credentials for this host so subsequent calls use them.
            await asyncio.to_thread(
                register_session,
                self.smb_host,
                username=self.smb_user,
                password=self.smb_pass,
                port=self.smb_port,
            )
            self._session_registered = True
        else:
            # Ensure local root exists (create if missing for parity with previous code)
            self.local_root.mkdir(parents=True, exist_ok=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session_registered:
            # Close cached connections; credentials remain in process memory until reset.
            await asyncio.to_thread(reset_connection_cache)
            self._session_registered = False

    # --------------------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------------------
    def _local_abspath(self, subpath: str) -> Path:
        return (self.local_root / subpath).resolve()

    def _smb_abspath(self, subpath: str) -> str:
        """
        Build a UNC path like:
            \\HOST\SHARE\sub\path
        Use smbclient.path.join to be safe across OSes.
        """
        # Normalize any forward slashes from callers into backslashes for UNC
        subpath = subpath.replace("/", "\\").lstrip("\\")
        # First join \\HOST\SHARE
        root = f"\\\\{self.smb_host}\\{self.smb_share}"
        # return smbpath.join(root, subpath) if subpath else root
        return root +"\\"+subpath if subpath else root
    async def _smb_exists(self, abs_unc: str) -> bool:
        return await asyncio.to_thread(smbpath.exists, abs_unc)

    async def _smb_is_dir(self, abs_unc: str) -> bool:
        try:
            st = await asyncio.to_thread(smbstat, abs_unc)
            # On Windows-like semantics, directories have st.st_mode with S_IFDIR
            # We rely on path.isdir (faster) to avoid bit-twiddling here.
            return await asyncio.to_thread(smbpath.isdir, abs_unc)
        except FileNotFoundError:
            return False

    async def _smb_is_file(self, abs_unc: str) -> bool:
        try:
            return await asyncio.to_thread(smbpath.isfile, abs_unc)
        except FileNotFoundError:
            return False

    # --------------------------------------------------------------------------
    # ASYNC FILE & FOLDER OPERATIONS
    # --------------------------------------------------------------------------
    async def list_dir(
        self,
        subpath: str = "",
        only_files: bool = False,
        only_dirs: bool = False,
        extension: Optional[str] = None,
        name_contains: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        List files/folders under a given subpath with optional filters.
        Mirrors your previous behavior.
        """
        entries: List[str] = []

        if self.use_local_fs:
            base = self._local_abspath(subpath)
            if not base.exists():
                raise FileNotFoundError(f"Path not found: {base}")
            for p in base.iterdir():
                if only_files and not p.is_file():
                    continue
                if only_dirs and not p.is_dir():
                    continue
                if extension and not p.name.endswith(extension):
                    continue
                if name_contains and name_contains.lower() not in p.name.lower():
                    continue
                if pattern and not fnmatch.fnmatch(p.name, pattern):
                    continue
                entries.append(p.name)
            return entries

        # SMB path
        abs_unc = self._smb_abspath(subpath)
        if not await self._smb_exists(abs_unc):
            raise FileNotFoundError(f"Path not found: {abs_unc}")

        def _scandir_list() -> List[SMBDirEntry]:
            return list(scandir(abs_unc))

        dirents = await asyncio.to_thread(_scandir_list)
        for de in dirents:
            name = de.name
            is_dir = de.is_dir()
            is_file = de.is_file()

            if only_files and not is_file:
                continue
            if only_dirs and not is_dir:
                continue
            if extension and not name.endswith(extension):
                continue
            if name_contains and name_contains.lower() not in name.lower():
                continue
            if pattern and not fnmatch.fnmatch(name, pattern):
                continue

            entries.append(name)
        return entries

    async def read_file(self, filepath: str, binary: bool = False) -> Union[str, bytes]:
        """Read a file (text or binary)."""
        if self.use_local_fs:
            full_path = self._local_abspath(filepath)
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {full_path}")
            mode = "rb" if binary else "r"
            async with aiofiles.open(full_path, mode) as f:
                return await f.read()

        abs_unc = self._smb_abspath(filepath)
        if not await self._smb_exists(abs_unc):
            raise FileNotFoundError(f"File not found: {abs_unc}")

        def _read():
            mode = "rb" if binary else "r"
            with open_file(abs_unc, mode=mode) as fd:
                return fd.read()

        content = await asyncio.to_thread(_read)
        return content

    async def write_file(
        self,
        filepath: str,
        content: Union[str, bytes],
        binary: bool = False,
        overwrite: bool = True,
    ) -> None:
        """Create or update a file."""
        if self.use_local_fs:
            full_path = self._local_abspath(filepath)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if full_path.exists() and not overwrite:
                raise FileExistsError(f"File already exists: {full_path}")
            mode = "wb" if binary else "w"
            async with aiofiles.open(full_path, mode) as f:
                await f.write(content)
            return

        abs_unc = self._smb_abspath(filepath)

        # Ensure parent directory exists (create if missing)
        parent, unc_parent = await self.get_unc_subpath(abs_unc) # smbpath.dirname(abs_unc)
        if not await self._smb_exists(unc_parent):
            await asyncio.to_thread(mkdir, parent)

        if (await self._smb_exists(abs_unc)) and not overwrite:
            raise FileExistsError(f"File already exists: {abs_unc}")

        def _write():
            mode = "wb" if binary else "w"
            with open_file(abs_unc, mode=mode) as fd:
                fd.write(content)

        await asyncio.to_thread(_write)

    async def delete_file(self, filepath: str) -> None:
        """Delete a file."""
        if self.use_local_fs:
            full_path = self._local_abspath(filepath)
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {full_path}")
            full_path.unlink()
            return

        abs_unc = self._smb_abspath(filepath)
        if not await self._smb_exists(abs_unc):
            raise FileNotFoundError(f"File not found: {abs_unc}")
        await asyncio.to_thread(remove, abs_unc)

    async def create_folder(self, folderpath: str) -> None:
        """Create a folder (all parents)."""
        if self.use_local_fs:
            self._local_abspath(folderpath).mkdir(parents=True, exist_ok=True)
            return

        abs_unc = self._smb_abspath(folderpath)
        await asyncio.to_thread(mkdir, abs_unc)

    async def delete_folder(self, folderpath: str) -> None:
        """Delete folder and its contents (recursive)."""
        if self.use_local_fs:
            full_path = self._local_abspath(folderpath)
            if not full_path.exists():
                raise FileNotFoundError(f"Folder not found: {full_path}")
            shutil.rmtree(full_path)
            return

        abs_unc = self._smb_abspath(folderpath)
        if not await self._smb_exists(abs_unc):
            raise FileNotFoundError(f"Folder not found: {abs_unc}")

        # Recursively remove contents then the folder itself
        async def _rm_tree(unc: str):
            # List entries
            def _listdir():
                return list(scandir(unc))
            try:
                entries = await asyncio.to_thread(_listdir)
            except FileNotFoundError:
                return

            for de in entries:
                child = unc + "\\" + de.name # smbpath.join(unc, de.name)
                if de.is_dir():
                    await _rm_tree(child)
                    await asyncio.to_thread(rmdir, child)
                else:
                    await asyncio.to_thread(remove, child)

        await _rm_tree(abs_unc)
        await asyncio.to_thread(rmdir, abs_unc)

    async def exists(self, path: str) -> bool:
        """Check existence of a file or folder."""
        if self.use_local_fs:
            return self._local_abspath(path).exists()
        abs_unc = self._smb_abspath(path)
        return await self._smb_exists(abs_unc)


    async def get_unc_subpath(self, unc_path: str) -> str:
        """
        Given a UNC path like \\host\share\folder\file.txt,
        return the subpath under the share (e.g., 'folder' or 'folder\\sub').
        """
        # Normalize and split
        parts = unc_path.strip("\\").split("\\")
        if len(parts) < 2:
            raise ValueError(f"Invalid UNC path: {unc_path}")
        
        # parts[0] = host, parts[1] = share
        # Everything after that is the subpath
        sub_parts = parts[2:-1] if len(parts) > 2 else []
        return "\\".join(sub_parts), "\\\\"+parts[0]+"\\"+parts[1]+"\\"+"\\".join(sub_parts)