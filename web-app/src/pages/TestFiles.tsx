import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Folder,
  FolderPlus,
  FolderUp,
  History,
  Lock,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  UserPlus,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

type ProjectRole = 'owner' | 'admin' | 'editor' | 'viewer';

interface WorkspaceProject {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  members: Record<string, ProjectRole>;
  updated_at: string;
}

interface FileLock {
  file_id?: string;
  user_id: string;
  token: string;
  checkout_version?: number;
  base_version?: number;
  source_version?: number;
  source_version_id?: string;
  based_on_history?: boolean;
  expires_at?: string;
  original_path?: string;
  original_name?: string;
  created_at: string;
}

interface WorkspaceFile {
  id: string;
  name: string;
  relative_path: string;
  is_directory: boolean;
  current_version?: number;
  size?: number;
  updated_at?: string;
  updated_by?: string;
  lock?: FileLock | null;
}

interface FileVersion {
  id: string;
  version: number;
  size: number;
  content_hash: string;
  created_by: string;
  created_at: string;
  base_version?: number;
  from_history?: boolean;
}

interface TrashFile {
  id: string;
  name: string;
  relative_path: string;
  is_directory: boolean;
  current_version?: number;
  size?: number;
  deleted_at: string;
  deleted_by?: string;
}

interface TreeNode {
  key: string;
  projectId: string;
  path: string;
  name: string;
  isRoot?: boolean;
  isTrash?: boolean;
  children: TreeNode[];
}

const projectKey = (projectId: string) => `${projectId}:`;
const dirKey = (projectId: string, path: string) => `${projectId}:${path}`;
const trashKey = (projectId: string) => `${projectId}:#trash`;

const TestFiles: React.FC = () => {
  const { token, user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const pendingPathRef = useRef('');
  const pendingTrashRef = useRef(false);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [directoriesByProject, setDirectoriesByProject] = useState<Record<string, string[]>>({});
  const [expandedPaths, setExpandedPaths] = useState<Record<string, boolean>>({});
  const [currentPath, setCurrentPath] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [historyFile, setHistoryFile] = useState<WorkspaceFile | null>(null);
  const [versions, setVersions] = useState<FileVersion[]>([]);
  const [checkingInId, setCheckingInId] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [deletingId, setDeletingId] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState('');
  const [confirmDeleteProject, setConfirmDeleteProject] = useState(false);
  const [showTrash, setShowTrash] = useState(false);
  const [trashFiles, setTrashFiles] = useState<TrashFile[]>([]);
  const [loadingTrash, setLoadingTrash] = useState(false);
  const [confirmEmptyTrash, setConfirmEmptyTrash] = useState(false);
  const [creatingDir, setCreatingDir] = useState(false);
  const [newDirName, setNewDirName] = useState('');
  const [menu, setMenu] = useState<{ node: TreeNode; x: number; y: number } | null>(null);
  const [uploadMenuOpen, setUploadMenuOpen] = useState(false);
  // null 表示未指定目标，上传到当前所在目录。
  const uploadTargetRef = useRef<string | null>(null);

  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${token || ''}` }),
    [token],
  );

  const selectedProject = projects.find(project => project.id === selectedProjectId);
  const role = selectedProject && user ? selectedProject.members[user.id] : undefined;
  const canEdit = role === 'owner' || role === 'admin' || role === 'editor';

  const requestJson = async (url: string, options: RequestInit = {}) => {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...authHeaders,
        ...(options.headers || {}),
      },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || data.status || '请求失败');
    }
    return data;
  };

  const loadAllDirectories = async (projectList: WorkspaceProject[]) => {
    const entries = await Promise.all(projectList.map(async project => {
      try {
        const data = await requestJson(`/api/workspace/projects/${project.id}/directories`);
        return [project.id, data.directories as string[]] as const;
      } catch {
        return [project.id, [] as string[]] as const;
      }
    }));
    setDirectoriesByProject(Object.fromEntries(entries));
  };

  const loadProjects = async (preferredId?: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await requestJson('/api/workspace/projects');
      setProjects(data.projects);
      await loadAllDirectories(data.projects);
      setSelectedProjectId(current => {
        const fallback = preferredId || current;
        if (fallback && data.projects.some((project: WorkspaceProject) => project.id === fallback)) {
          return fallback;
        }
        return data.projects[0]?.id || '';
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '项目加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadFiles = async (projectId = selectedProjectId, path = currentPath) => {
    if (!projectId) {
      setFiles([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await requestJson(
        `/api/workspace/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
      );
      setFiles(data.files);
    } catch (err) {
      setError(err instanceof Error ? err.message : '文件加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadDirectories = async (projectId = selectedProjectId) => {
    const target = projects.find(project => project.id === projectId);
    if (!target) return;
    try {
      const data = await requestJson(`/api/workspace/projects/${target.id}/directories`);
      setDirectoriesByProject(current => ({ ...current, [target.id]: data.directories }));
    } catch {
      setDirectoriesByProject(current => ({ ...current, [target.id]: [] }));
    }
  };

  const loadTrash = async (projectId = selectedProjectId) => {
    if (!projectId) {
      setTrashFiles([]);
      return;
    }
    setLoadingTrash(true);
    try {
      const data = await requestJson(`/api/workspace/projects/${projectId}/trash`);
      setTrashFiles(data.files);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '回收站加载失败');
    } finally {
      setLoadingTrash(false);
    }
  };

  const openTrash = (projectId: string) => {
    setShowTrash(true);
    setConfirmEmptyTrash(false);
    setTrashFiles([]);
    loadTrash(projectId);
  };

  const restoreTrashFile = async (file: TrashFile) => {
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/files/${file.id}/restore`, { method: 'POST' });
      setActionMessage(`已恢复 ${file.name}`);
      await loadTrash();
      await loadFiles();
      await loadDirectories();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '恢复失败');
    }
  };

  const purgeTrashFile = async (file: TrashFile) => {
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/files/${file.id}/purge`, { method: 'DELETE' });
      setActionMessage(`已彻底删除 ${file.name}`);
      await loadTrash();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '彻底删除失败');
    }
  };

  const emptyTrash = async () => {
    setActionMessage('');
    try {
      const data = await requestJson(`/api/workspace/projects/${selectedProjectId}/trash`, { method: 'DELETE' });
      setActionMessage(data.count ? `已清空回收站，共彻底删除 ${data.count} 项` : '回收站已经为空');
      setConfirmEmptyTrash(false);
      await loadTrash();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '清空回收站失败');
    }
  };

  useEffect(() => {
    if (token) loadProjects();
  }, [token]);

  useEffect(() => {
    setHistoryFile(null);
    setConfirmDeleteId('');
    setConfirmDeleteProject(false);
    setConfirmEmptyTrash(false);
    // 切换项目时由 selectNode 指定目标是目录还是回收站，其余情况回到项目根目录。
    const pendingPath = pendingPathRef.current;
    const pendingTrash = pendingTrashRef.current;
    pendingPathRef.current = '';
    pendingTrashRef.current = false;
    if (pendingTrash) {
      setCurrentPath('');
      setShowTrash(true);
      setTrashFiles([]);
      loadTrash(selectedProjectId);
    } else {
      setShowTrash(false);
      setTrashFiles([]);
      setCurrentPath(pendingPath);
    }
    if (selectedProjectId) loadFiles(selectedProjectId, pendingPath);
    else setFiles([]);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId || !token) return;
    const heartbeat = async () => {
      const ownedLocks = files.filter(file => file.lock?.user_id === user?.id && Boolean(file.lock?.token));
      await Promise.all(ownedLocks.map(async file => {
        try {
          await requestJson(`/api/workspace/files/${file.id}/checkout/heartbeat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: file.lock?.token }),
          });
        } catch {
          // 文件可能已经检入或检出已失效，刷新列表即可同步状态。
        }
      }));
    };
    const timer = window.setInterval(heartbeat, 30 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [files, selectedProjectId, token, user?.id]);

  const createProject = async () => {
    const name = window.prompt('请输入项目名称');
    if (!name?.trim()) return;
    try {
      const data = await requestJson('/api/workspace/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      });
      setProjects(current => [data.project, ...current]);
      setDirectoriesByProject(current => ({ ...current, [data.project.id]: [] }));
      setSelectedProjectId(data.project.id);
      setExpandedPaths(current => ({ ...current, [projectKey(data.project.id)]: true }));
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '创建项目失败');
    }
  };

  const addMember = async () => {
    if (!selectedProjectId) return;
    const userId = window.prompt('请输入成员用户 ID');
    if (!userId?.trim()) return;
    try {
      const data = await requestJson(`/api/workspace/projects/${selectedProjectId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId.trim(), role: 'editor' }),
      });
      setProjects(current => current.map(project => project.id === data.project.id ? data.project : project));
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '添加成员失败');
    }
  };

  const uploadFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || []);
    if (!selectedProjectId || selectedFiles.length === 0) return;
    // 右键/下拉菜单指定目标目录，否则上传到当前所在目录。
    const targetPath = uploadTargetRef.current ?? currentPath;
    uploadTargetRef.current = null;
    setUploading(true);
    try {
      for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        // 整目录上传时浏览器会提供带层级的内置路径，按原结构保留；普通上传只用文件名。
        const relativeName = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
        formData.append('relative_path', [targetPath, relativeName].filter(Boolean).join('/'));
        const response = await fetch(`/api/workspace/projects/${selectedProjectId}/files`, {
          method: 'POST',
          headers: authHeaders,
          body: formData,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || data.status || `${file.name} 上传失败`);
      }
      await loadFiles(selectedProjectId, targetPath);
      await loadDirectories();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (folderInputRef.current) folderInputRef.current.value = '';
    }
  };

  const createDirectory = async (parentPath: string, name: string) => {
    const trimmed = name.trim();
    if (!selectedProjectId || !trimmed) return;
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/projects/${selectedProjectId}/directories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: [parentPath, trimmed].filter(Boolean).join('/') }),
      });
      setCreatingDir(false);
      setNewDirName('');
      setActionMessage(`已新建文件夹 ${trimmed}`);
      await loadFiles(selectedProjectId, parentPath);
      await loadDirectories();
      const key = dirKey(selectedProjectId, [parentPath, trimmed].filter(Boolean).join('/'));
      setExpandedPaths(current => ({ ...current, [key]: true }));
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '新建文件夹失败');
    }
  };

  // 统一上传入口：文件与文件夹共用一套选目标目录逻辑，仅在选择器上区分。
  const uploadToDirectory = (directoryPath: string, asFolder = false) => {
    if (directoryPath !== currentPath) gotoPath(directoryPath);
    uploadTargetRef.current = directoryPath;
    setMenu(null);
    setUploadMenuOpen(false);
    if (asFolder) folderInputRef.current?.click();
    else fileInputRef.current?.click();
  };

  const startUpload = (asFolder: boolean) => {
    setUploadMenuOpen(false);
    uploadTargetRef.current = null;
    if (asFolder) folderInputRef.current?.click();
    else fileInputRef.current?.click();
  };

  const downloadClient = () => {
    window.location.href = '/api/client/download';
  };

  const downloadFile = async (file: WorkspaceFile) => {
    const response = await fetch(`/api/workspace/files/${file.id}/content`, { headers: authHeaders });
    if (!response.ok) {
      setActionMessage('下载失败');
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = file.name;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const showVersions = async (file: WorkspaceFile) => {
    try {
      const data = await requestJson(`/api/workspace/files/${file.id}/versions`);
      setHistoryFile(file);
      setVersions(data.versions);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '版本历史加载失败');
    }
  };

  const checkoutFile = async (file: WorkspaceFile, versionId?: string) => {
    setActionMessage('');
    if (file.lock && file.lock.user_id !== user?.id) {
      setActionMessage(`文件正在被 ${file.lock.user_id} 检出，暂时无法打开`);
      return;
    }
    try {
      const data = await requestJson(`/api/workspace/files/${file.id}/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(versionId ? { version_id: versionId } : {}),
      });
      const lock = data.lock as FileLock;
      const payload = {
        server_url: window.location.origin,
        token,
        file_id: file.id,
        checkout_token: lock.token,
        checkout_version: lock.checkout_version ?? lock.base_version ?? file.current_version ?? 0,
        project_id: selectedProjectId,
        file_name: file.name,
        relative_path: file.relative_path,
      };
      try {
        const localResponse = await fetch('http://127.0.0.1:17890/open', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
        const localData = await localResponse.json();
        if (!localResponse.ok) throw new Error(localData.message || '本地打开器打开失败');
        setActionMessage(
          lock.based_on_history
            ? `已基于 v${lock.source_version} 检出，保存并点击“检入”后将在最新版 v${file.current_version} 之上升版。`
            : '文件已打开，请在本地软件中保存，完成后回到网页点击“检入”。',
        );
      } catch {
        const query = new URLSearchParams({ server_url: payload.server_url, token: token || '', file_id: file.id, checkout_token: lock.token, project_id: selectedProjectId, file_name: file.name, relative_path: file.relative_path });
        window.location.href = `yishexu://open?${query.toString()}`;
        setActionMessage('本地服务未响应，已尝试启动打开器协议；请启动客户端后重试。');
      }
      await loadFiles();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '检出失败');
    }
  };

  const checkinFile = async (file: WorkspaceFile) => {
    const checkoutToken = file.lock?.token;
    if (!checkoutToken) return;
    setCheckingInId(file.id);
    const payload = { server_url: window.location.origin, token, file_id: file.id, checkout_token: checkoutToken, project_id: selectedProjectId, file_name: file.name };
    try {
      let localServiceUnavailable = false;
      try {
        const response = await fetch('http://127.0.0.1:17890/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok) {
          setActionMessage(data.message || '检入失败');
          return;
        }
        setActionMessage('文件已成功检入并生成新版本，专用临时文件已删除');
        await loadFiles();
      } catch {
        localServiceUnavailable = true;
      }
      if (localServiceUnavailable) {
        const query = new URLSearchParams({ server_url: payload.server_url, token: token || '', file_id: file.id, checkout_token: checkoutToken, project_id: selectedProjectId, file_name: file.name });
        window.location.href = `yishexu://checkin?${query.toString()}`;
        setActionMessage('客户端未响应，已尝试启动检入协议；客户端完成后请刷新文件状态。');
      }
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '检入失败');
    } finally {
      setCheckingInId('');
    }
  };

  const cancelCheckout = async (file: WorkspaceFile) => {
    setActionMessage('');
    try {
      const response = await fetch('http://127.0.0.1:17890/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: file.id, checkout_token: file.lock?.token }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || '取消检出失败');
      setActionMessage('已取消检出');
      await loadFiles();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '取消检出失败');
    }
  };

  const deleteFile = async (file: WorkspaceFile) => {
    setDeletingId(file.id);
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/files/${file.id}`, { method: 'DELETE' });
      setActionMessage(`已将 ${file.name} 移入回收站`);
      setConfirmDeleteId('');
      await loadFiles();
      await loadDirectories();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '删除失败');
    } finally {
      setDeletingId('');
    }
  };

  const deleteDirectory = async (directory: WorkspaceFile) => {
    setDeletingId(directory.id);
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/projects/${selectedProjectId}/directories`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: directory.relative_path }),
      });
      setActionMessage(`已将目录 ${directory.name} 移入回收站`);
      setConfirmDeleteId('');
      await loadFiles();
      await loadDirectories();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '删除目录失败');
    } finally {
      setDeletingId('');
    }
  };

  // 右键菜单删除目录：目录路径由树节点直接提供，无需先进入该目录。
  const deleteDirectoryByPath = async (path: string) => {
    setMenu(null);
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/projects/${selectedProjectId}/directories`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      setActionMessage(`${path} 已移入回收站`);
      // 当前正在查看被删目录或其子目录时，退回项目根目录。
      const stillExists = currentPath !== path && !currentPath.startsWith(`${path}/`);
      await loadFiles(selectedProjectId, stillExists ? currentPath : '');
      if (!stillExists) setCurrentPath('');
      await loadDirectories();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '删除文件夹失败');
    }
  };

  const deleteProject = async () => {
    if (!selectedProject) return;
    setActionMessage('');
    try {
      await requestJson(`/api/workspace/projects/${selectedProject.id}`, { method: 'DELETE' });
      setActionMessage(`已删除项目 ${selectedProject.name}`);
      setConfirmDeleteProject(false);
      setSelectedProjectId('');
      await loadProjects('');
      setExpandedPaths(current => {
        const next = { ...current };
        delete next[projectKey(selectedProject.id)];
        return next;
      });
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '删除项目失败');
    }
  };

  const downloadVersion = async (version: FileVersion) => {
    if (!historyFile) return;
    const response = await fetch(
      `/api/workspace/files/${historyFile.id}/versions/${version.id}/content`,
      { headers: authHeaders },
    );
    if (!response.ok) {
      setActionMessage('历史版本下载失败');
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `v${version.version}_${historyFile.name}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const filteredFiles = files.filter(file => file.name.toLowerCase().includes(searchTerm.toLowerCase()));
  const pathParts = currentPath ? currentPath.split('/') : [];

  const gotoPath = (target: string) => {
    setShowTrash(false);
    setCurrentPath(target);
    setCreatingDir(false);
    setNewDirName('');
    loadFiles(selectedProjectId, target);
    // 展开目标路径的所有上级目录，保证当前目录在树中可见。
    setExpandedPaths(current => {
      const next = { ...current, [dirKey(selectedProjectId, target)]: true };
      if (target) {
        const parts = target.split('/');
        parts.forEach((_, index) => {
          next[dirKey(selectedProjectId, parts.slice(0, index + 1).join('/'))] = true;
        });
      }
      return next;
    });
  };

  const toggleExpand = (key: string) => {
    setExpandedPaths(current => ({ ...current, [key]: !current[key] }));
  };

  // 把每个项目的扁平目录列表组装成树，项目本身作为根节点（容器），回收站作为项目内固定节点。
  const treeNodes = useMemo(() => {
    return projects.map(project => {
      const directories = directoriesByProject[project.id] || [];
      const nodes: TreeNode[] = directories.map(path => ({
        key: dirKey(project.id, path),
        projectId: project.id,
        path,
        name: path.split('/').pop() || path,
        children: [],
      }));
      const byPath = new Map(nodes.map(node => [node.path, node]));
      const children: TreeNode[] = [];
      nodes.forEach(node => {
        const parentPath = node.path.includes('/') ? node.path.slice(0, node.path.lastIndexOf('/')) : '';
        const parent = parentPath ? byPath.get(parentPath) : undefined;
        if (parent) parent.children.push(node);
        else children.push(node);
      });
      children.push({
        key: trashKey(project.id),
        projectId: project.id,
        path: '',
        name: '回收站',
        isTrash: true,
        children: [],
      });
      return {
        key: projectKey(project.id),
        projectId: project.id,
        path: '',
        name: project.name,
        isRoot: true,
        children,
      } as TreeNode;
    });
  }, [projects, directoriesByProject]);

  const selectNode = (node: TreeNode) => {
    // 回收站节点：切到目标项目并打开其回收站。
    if (node.isTrash) {
      if (node.projectId === selectedProjectId) {
        openTrash(node.projectId);
      } else {
        pendingTrashRef.current = true;
        setSelectedProjectId(node.projectId);
      }
      return;
    }
    setShowTrash(false);
    if (node.projectId === selectedProjectId) {
      setCurrentPath(node.path);
      loadFiles(node.projectId, node.path);
    } else {
      pendingPathRef.current = node.path;
      setSelectedProjectId(node.projectId);
    }
    // 展开路径上的所有上级节点，保证被选中的目录在树中可见。
    setExpandedPaths(current => {
      const next = { ...current, [node.key]: true };
      if (node.path) {
        const parts = node.path.split('/');
        parts.forEach((_, index) => {
          next[dirKey(node.projectId, parts.slice(0, index + 1).join('/'))] = true;
        });
      }
      return next;
    });
  };

  const renderTree = (nodes: TreeNode[], depth: number): React.ReactNode => (
    nodes.map(node => {
      const expanded = Boolean(expandedPaths[node.key]);
      const isActive = node.projectId === selectedProjectId
        && (node.isTrash
          ? showTrash
          : node.isRoot ? (!currentPath && !showTrash) : (!showTrash && node.path === currentPath));
      const hasChildren = node.children.length > 0;
      // 回收站节点不支持文件夹操作，其余目录节点均可用右键菜单。
      const showMenu = canEdit && !node.isTrash;
      return (
        <div key={node.key}>
          <div
            className={`flex items-center rounded ${isActive ? 'bg-brb-blue-50 text-brb-blue-700' : 'hover:bg-gray-100'}`}
            style={{ paddingLeft: `${depth * 12 + 6}px` }}
            onContextMenu={showMenu ? event => {
              event.preventDefault();
              setMenu({ node, x: event.clientX, y: event.clientY });
            } : undefined}
          >
            <button
              onClick={() => toggleExpand(node.key)}
              className={`shrink-0 rounded p-0.5 text-gray-400 hover:text-gray-600 ${hasChildren ? '' : 'invisible'}`}
              title={expanded ? '收起' : '展开'}
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            <button
              onClick={() => selectNode(node)}
              className="flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-2 text-left text-sm"
            >
              {node.isTrash
                ? <Trash2 className="shrink-0 text-gray-400" size={15} />
                : <Folder className={`shrink-0 ${node.isRoot ? 'text-brb-blue-600' : 'text-amber-500'}`} size={15} />}
              <span className={`truncate ${node.isRoot ? 'font-semibold' : ''}`}>{node.name}</span>
            </button>
          </div>
          {expanded && renderTree(node.children, depth + 1)}
        </div>
      );
    })
  );

  return (
    <div className="fade-in mx-5 flex h-[calc(100vh-6rem)] gap-3">
      <aside className="flex w-64 shrink-0 flex-col overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="flex items-center justify-between gap-1 border-b border-gray-200 px-2 py-1.5">
          <span className="truncate pl-1 text-xs font-medium uppercase tracking-wide text-gray-500">项目容器</span>
          <span className="flex shrink-0 items-center gap-0.5">
            <button title="新建项目" onClick={createProject} className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100">
              <Plus size={16} />
            </button>
            {canEdit && (
              <button title="添加成员" onClick={addMember} className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100">
                <UserPlus size={16} />
              </button>
            )}
            {role === 'owner' && (
              <button title="删除项目" onClick={() => setConfirmDeleteProject(true)} className="rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600">
                <Trash2 size={16} />
              </button>
            )}
          </span>
        </div>

        {confirmDeleteProject && selectedProject && (
          <div className="flex items-center justify-between gap-1 border-b border-red-100 bg-red-50 px-2 py-1.5">
            <span className="truncate text-xs text-red-700">删除项目「{selectedProject.name}」？</span>
            <span className="flex shrink-0 items-center gap-0.5">
              <button onClick={deleteProject} className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-100">确认</button>
              <button onClick={() => setConfirmDeleteProject(false)} className="rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100">取消</button>
            </span>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-auto py-1">
          {treeNodes.length > 0
            ? renderTree(treeNodes, 0)
            : <div className="px-3 py-2 text-xs text-gray-400">{loading ? '加载中' : '暂无项目，点击右上角 + 新建'}</div>}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-gray-200 bg-white px-3 py-2">
          {showTrash ? (
            <>
              <button
                title="返回文件列表"
                onClick={() => setShowTrash(false)}
                className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100"
              >
                <ChevronLeft size={17} />
              </button>
              <div className="flex min-w-0 flex-1 items-center gap-1.5 truncate text-sm text-gray-700">
                <Trash2 size={15} className="shrink-0 text-gray-500" />
                <span className="truncate font-medium">{selectedProject?.name} · 回收站</span>
              </div>
            </>
          ) : (
            <>
              <button
                title="上一级"
                disabled={!currentPath}
                onClick={() => gotoPath(pathParts.slice(0, -1).join('/'))}
                className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
              >
                <ChevronLeft size={17} />
              </button>
              <div className="flex min-w-0 flex-1 items-center truncate text-sm text-gray-600">
                <button onClick={() => gotoPath('')} className="shrink-0 rounded px-1 py-0.5 hover:bg-gray-100">{selectedProject?.name || '根目录'}</button>
                {pathParts.map((part, index) => {
                  const target = pathParts.slice(0, index + 1).join('/');
                  return (
                    <React.Fragment key={target}>
                      <span className="shrink-0 text-gray-400">/</span>
                      <button onClick={() => gotoPath(target)} className="truncate rounded px-1 py-0.5 hover:bg-gray-100">{part}</button>
                    </React.Fragment>
                  );
                })}
              </div>

              <div className="relative shrink-0">
                <Search className="absolute left-2 top-1.5 text-gray-400" size={15} />
                <input
                  className="w-44 rounded-md border border-gray-300 py-1.5 pl-7 pr-2 text-sm focus:border-brb-blue-500 focus:outline-none"
                  value={searchTerm}
                  onChange={event => setSearchTerm(event.target.value)}
                  placeholder="搜索当前目录"
                />
              </div>
              {canEdit && (
                <>
                  <input ref={fileInputRef} type="file" multiple className="hidden" onChange={uploadFiles} />
                  <input
                    ref={folderInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={uploadFiles}
                    {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
                  />
                  <div className="relative shrink-0">
                    <button
                      title={uploading ? '上传中' : '上传'}
                      disabled={uploading}
                      onClick={() => setUploadMenuOpen(open => !open)}
                      className="flex items-center rounded-md p-1.5 text-brb-blue-600 hover:bg-brb-blue-50 disabled:opacity-60"
                    >
                      <Upload size={17} />
                      <ChevronDown size={13} />
                    </button>
                    {uploadMenuOpen && (
                      <>
                        <div className="fixed inset-0 z-40" onClick={() => setUploadMenuOpen(false)} />
                        <div className="absolute right-0 top-full z-50 mt-1 min-w-[7.5rem] rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                          <button
                            onClick={() => startUpload(false)}
                            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
                          >
                            <Upload size={15} className="text-gray-500" />上传文件
                          </button>
                          <button
                            onClick={() => startUpload(true)}
                            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
                          >
                            <FolderUp size={15} className="text-gray-500" />上传文件夹
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                  <button
                    title="新建文件夹"
                    onClick={() => { setCreatingDir(true); setNewDirName(''); }}
                    className="rounded-md p-1.5 text-amber-600 hover:bg-amber-50"
                  >
                    <FolderPlus size={17} />
                  </button>
                </>
              )}
            </>
          )}
          {showTrash && canEdit && (
            <button
              title="清空回收站"
              disabled={trashFiles.length === 0}
              onClick={() => setConfirmEmptyTrash(true)}
              className="rounded-md px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-40"
            >
              清空回收站
            </button>
          )}
              <button
                title="下载本地客户端"
                onClick={downloadClient}
                className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-brb-blue-700 hover:bg-brb-blue-50"
              >
                <Download size={15} />客户端
              </button>
              <button
                title="刷新"
                onClick={() => {
              if (showTrash) { loadTrash(); return; }
              loadProjects(selectedProjectId);
              if (selectedProjectId) loadFiles();
            }}
            className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100"
          >
            <RefreshCw size={17} />
          </button>
        </div>

        {!showTrash && creatingDir && (
          <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-3 py-1.5">
            <FolderPlus size={15} className="shrink-0 text-amber-600" />
            <span className="shrink-0 text-xs text-gray-600">{currentPath || selectedProject?.name || '根目录'} /</span>
            <input
              autoFocus
              value={newDirName}
              onChange={event => setNewDirName(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') createDirectory(currentPath, newDirName);
                if (event.key === 'Escape') { setCreatingDir(false); setNewDirName(''); }
              }}
              placeholder="输入文件夹名称后回车"
              className="min-w-0 flex-1 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brb-blue-500 focus:outline-none"
            />
            <button
              onClick={() => createDirectory(currentPath, newDirName)}
              disabled={!newDirName.trim()}
              className="shrink-0 rounded px-1.5 py-0.5 text-xs font-medium text-brb-blue-700 hover:bg-brb-blue-100 disabled:opacity-40"
            >
              确定
            </button>
            <button
              onClick={() => { setCreatingDir(false); setNewDirName(''); }}
              className="shrink-0 rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
            >
              取消
            </button>
          </div>
        )}

        {showTrash && confirmEmptyTrash && (
          <div className="flex items-center justify-between gap-1 border-b border-red-100 bg-red-50 px-3 py-1.5">
            <span className="text-xs text-red-700">确定清空回收站？其中的内容将被永久删除且无法恢复。</span>
            <span className="flex shrink-0 items-center gap-0.5">
              <button onClick={emptyTrash} className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-100">确认清空</button>
              <button onClick={() => setConfirmEmptyTrash(false)} className="rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100">取消</button>
            </span>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-auto bg-white">
          {showTrash ? (
            loadingTrash ? (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">加载中</div>
            ) : trashFiles.length > 0 ? (
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">名称</th>
                    <th className="px-3 py-2 font-medium">原路径</th>
                    <th className="w-20 px-3 py-2 font-medium">大小</th>
                    <th className="w-44 px-3 py-2 font-medium">删除时间</th>
                    <th className="px-3 py-2 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {trashFiles.map(file => (
                    <tr key={file.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-1.5">
                        <span className="flex items-center gap-2 font-medium text-gray-500">
                          {file.is_directory ? <Folder size={18} className="text-amber-500" /> : <FileText size={18} />}
                          <span className="line-through decoration-gray-400">{file.name}</span>
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-xs text-gray-500">{file.relative_path}</td>
                      <td className="px-3 py-1.5 text-gray-600">{file.is_directory ? '目录' : `${Math.max(1, Math.ceil((file.size || 0) / 1024))} KB`}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-500">{new Date(file.deleted_at).toLocaleString()}</td>
                      <td className="px-3 py-1.5">
                        <div className="flex items-center justify-end gap-0.5">
                          {canEdit && (
                            <>
                              <button title="恢复到原路径" onClick={() => restoreTrashFile(file)} className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50">
                                <RotateCcw size={13} />恢复
                              </button>
                              <button title="彻底删除，无法恢复" onClick={() => purgeTrashFile(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50">彻底删除</button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">回收站为空</div>
            )
          ) : selectedProject ? (
            filteredFiles.length > 0 ? (
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">名称</th>
                    <th className="w-16 px-3 py-2 font-medium">版本</th>
                    <th className="w-20 px-3 py-2 font-medium">大小</th>
                    <th className="w-32 px-3 py-2 font-medium">协作状态</th>
                    <th className="px-3 py-2 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFiles.map(file => (
                    <tr key={file.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-1.5">
                        <button
                          className="flex items-center gap-2 font-medium text-gray-900"
                          onClick={() => file.is_directory ? gotoPath(file.relative_path) : checkoutFile(file)}
                        >
                          {file.is_directory ? <Folder className="text-amber-500" size={18} /> : <FileText className="text-brb-blue-600" size={18} />}
                          {file.name}
                        </button>
                      </td>
                      <td className="px-3 py-1.5 text-gray-600">{file.is_directory ? '—' : `v${file.current_version}`}</td>
                      <td className="px-3 py-1.5 text-gray-600">{file.is_directory ? '—' : `${Math.max(1, Math.ceil((file.size || 0) / 1024))} KB`}</td>
                      <td className="px-3 py-1.5">
                        {file.lock
                          ? <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700"><Lock size={12} />{file.lock.user_id === user?.id ? '我正在编辑' : `${file.lock.user_id} 已检出`}</span>
                          : !file.is_directory && <span className="text-xs text-green-600">可检出</span>}
                      </td>
                      <td className="px-3 py-1.5">
                        <div className="flex items-center justify-end gap-0.5">
                          {file.is_directory ? (
                            <>
                              <button title="打开目录" onClick={() => gotoPath(file.relative_path)} className="rounded px-1.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50">打开</button>
                              {canEdit && (confirmDeleteId === file.id ? (
                                <>
                                  <button disabled={deletingId === file.id} title="确认删除目录" onClick={() => deleteDirectory(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60">{deletingId === file.id ? '删除中' : '确认删除'}</button>
                                  <button title="取消" onClick={() => setConfirmDeleteId('')} className="rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100">取消</button>
                                </>
                              ) : (
                                <button title="删除目录" onClick={() => setConfirmDeleteId(file.id)} className="rounded p-1 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={15} /></button>
                              ))}
                            </>
                          ) : (
                            <>
                              {!file.lock && <button title="检出并用本地软件打开" onClick={() => checkoutFile(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50">打开</button>}
                              {file.lock?.user_id === user?.id && (
                                <>
                                  <button disabled={checkingInId === file.id} title="检入" onClick={() => checkinFile(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-green-700 hover:bg-green-50">{checkingInId === file.id ? '检入中' : '检入'}</button>
                                  <button title="取消检出" onClick={() => cancelCheckout(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-50">取消检出</button>
                                </>
                              )}
                              <button title="版本历史" onClick={() => showVersions(file)} className="rounded p-1 text-gray-500 hover:bg-gray-100"><History size={15} /></button>
                              <button title="下载" onClick={() => downloadFile(file)} className="rounded p-1 text-gray-500 hover:bg-gray-100"><Download size={15} /></button>
                              {canEdit && (confirmDeleteId === file.id ? (
                                <>
                                  <button disabled={deletingId === file.id} title="确认删除" onClick={() => deleteFile(file)} className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60">{deletingId === file.id ? '删除中' : '确认删除'}</button>
                                  <button title="取消" onClick={() => setConfirmDeleteId('')} className="rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100">取消</button>
                                </>
                              ) : (
                                <button title="删除" onClick={() => setConfirmDeleteId(file.id)} className="rounded p-1 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={15} /></button>
                              ))}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-gray-400">
                {loading ? '加载中' : '当前目录暂无文件'}
              </div>
            )
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-gray-400">请选择或新建项目</div>
          )}
        </div>

        <div className="flex h-7 shrink-0 items-center border-t border-gray-200 bg-white px-3 text-xs">
          {error
            ? <span className="text-red-600">{error}</span>
            : actionMessage
              ? <span className="text-blue-700">{actionMessage}</span>
              : <span className="text-gray-400">就绪</span>}
        </div>
      </section>

      {menu && (
        <div className="fixed inset-0 z-40" onClick={() => setMenu(null)} onContextMenu={event => { event.preventDefault(); setMenu(null); }}>
          <div
            className="absolute min-w-[9rem] rounded-md border border-gray-200 bg-white py-1 shadow-lg"
            style={{ left: menu.x, top: menu.y }}
            onClick={event => event.stopPropagation()}
          >
            <div className="truncate px-3 py-1 text-xs text-gray-400">{menu.node.isRoot ? '项目根目录' : menu.node.path}</div>
            <button
              onClick={() => { setCreatingDir(true); setNewDirName(''); setMenu(null); }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
            >
              <FolderPlus size={15} className="text-gray-500" />新建子文件夹
            </button>
            <button
              onClick={() => uploadToDirectory(menu.node.path)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
            >
              <Upload size={15} className="text-gray-500" />上传文件到此目录
            </button>
            <button
              onClick={() => uploadToDirectory(menu.node.path, true)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
            >
              <FolderUp size={15} className="text-gray-500" />上传文件夹到此目录
            </button>
            {!menu.node.isRoot && (
              <button
                onClick={() => deleteDirectoryByPath(menu.node.path)}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-red-700 hover:bg-red-50"
              >
                <Trash2 size={15} />删除文件夹
              </button>
            )}
          </div>
        </div>
      )}

      {historyFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setHistoryFile(null)}>
          <div className="card max-h-[80vh] w-full max-w-2xl overflow-auto p-4" onClick={event => event.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold">{historyFile.name} · 版本历史</h3>
              <button onClick={() => setHistoryFile(null)} className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100">关闭</button>
            </div>
            <div className="mt-3 space-y-2">
              {versions.map(version => (
                <div key={version.id} className="rounded-lg border border-gray-200 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <strong className="text-sm">v{version.version}</strong>
                    <span className="text-xs text-gray-500">{new Date(version.created_at).toLocaleString()}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">提交人：{version.created_by} · {(version.size / 1024).toFixed(1)} KB{version.from_history ? ` · 基于 v${version.base_version} 修订` : ''}</div>
                  <div className="truncate font-mono text-xs text-gray-400">SHA-256: {version.content_hash || '旧版本未记录'}</div>
                  {version.version !== historyFile.current_version && (
                    <div className="mt-1.5 flex justify-end gap-0.5">
                      <button onClick={() => { const target = historyFile; setHistoryFile(null); checkoutFile(target, version.id); }} className="rounded px-1.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50">打开编辑</button>
                      <button onClick={() => downloadVersion(version)} className="rounded px-1.5 py-0.5 text-xs font-medium text-gray-600 hover:bg-gray-100">下载</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestFiles;
