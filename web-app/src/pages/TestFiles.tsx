import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronLeft,
  Download,
  FileText,
  Folder,
  FolderOpen,
  History,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  UserPlus,
  Users,
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

const TestFiles: React.FC = () => {
  const { token, user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
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

  const loadProjects = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await requestJson('/api/workspace/projects');
      setProjects(data.projects);
      setSelectedProjectId(current => {
        if (current && data.projects.some((project: WorkspaceProject) => project.id === current)) {
          return current;
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

  useEffect(() => {
    if (token) loadProjects();
  }, [token]);

  useEffect(() => {
    setCurrentPath('');
    setHistoryFile(null);
    setConfirmDeleteId('');
    setConfirmDeleteProject(false);
    if (selectedProjectId) loadFiles(selectedProjectId, '');
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
      setSelectedProjectId(data.project.id);
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
    setUploading(true);
    try {
      for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('relative_path', [currentPath, file.name].filter(Boolean).join('/'));
        const response = await fetch(`/api/workspace/projects/${selectedProjectId}/files`, {
          method: 'POST',
          headers: authHeaders,
          body: formData,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || data.status || `${file.name} 上传失败`);
      }
      await loadFiles();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
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
      setActionMessage(`已删除 ${file.name}`);
      setConfirmDeleteId('');
      await loadFiles();
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
      setActionMessage(`已删除目录 ${directory.name}`);
      setConfirmDeleteId('');
      await loadFiles();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : '删除目录失败');
    } finally {
      setDeletingId('');
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
      await loadProjects();
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

  return (
    <div className="space-y-5 fade-in">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">协同文件中心</h1>
          <p className="mt-1 text-sm text-gray-500">点击文件检出，在本地默认软件中编辑并保存，完成后回到网页检入；版本历史和下载仍可用。</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary flex items-center gap-2 py-2 px-4" onClick={loadProjects}>
            <RefreshCw size={17} />刷新
          </button>
          <button className="btn-primary flex items-center gap-2 py-2 px-4" onClick={createProject}>
            <Plus size={17} />新建项目
          </button>
        </div>
      </div>

      {actionMessage && <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">{actionMessage}</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="grid min-h-[620px] gap-5 lg:grid-cols-[260px_1fr]">
        <aside className="card p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700">
            <FolderOpen size={18} />项目空间
          </div>
          <div className="space-y-2">
            {projects.map(project => (
              <button
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                className={`w-full rounded-lg border px-3 py-3 text-left transition ${selectedProjectId === project.id ? 'border-brb-blue-300 bg-brb-blue-50' : 'border-transparent hover:bg-gray-50'}`}
              >
                <div className="truncate font-medium text-gray-900">{project.name}</div>
                <div className="mt-1 flex items-center gap-1 text-xs text-gray-500"><Users size={13} />{Object.keys(project.members).length} 位成员</div>
              </button>
            ))}
            {!loading && projects.length === 0 && <div className="py-8 text-center text-sm text-gray-400">暂无项目</div>}
          </div>
        </aside>

        <main className="card overflow-hidden">
          {selectedProject ? (
            <>
              <div className="border-b border-gray-200 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">{selectedProject.name}</h2>
                    <p className="mt-1 text-xs text-gray-500">当前角色：{role || '成员'} · 文件保存将生成独立版本</p>
                  </div>
                  <div className="flex gap-2">
                    {(role === 'owner' || role === 'admin') && (
                      <button className="btn-secondary flex items-center gap-2 py-2 px-4" onClick={addMember}>
                        <UserPlus size={17} />添加成员
                      </button>
                    )}
                    {role === 'owner' && (
                      confirmDeleteProject ? (
                        <div className="flex items-center gap-2">
                          <button className="btn-secondary flex items-center gap-2 py-2 px-4 text-red-700" onClick={deleteProject}>
                            <Trash2 size={17} />确认删除项目
                          </button>
                          <button className="btn-secondary py-2 px-4" onClick={() => setConfirmDeleteProject(false)}>取消</button>
                        </div>
                      ) : (
                        <button className="btn-secondary flex items-center gap-2 py-2 px-4" onClick={() => setConfirmDeleteProject(true)}>
                          <Trash2 size={17} />删除项目
                        </button>
                      )
                    )}
                    {canEdit && (
                      <>
                        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={uploadFiles} />
                        <button disabled={uploading} className="btn-primary flex items-center gap-2 py-2 px-4 disabled:opacity-60" onClick={() => fileInputRef.current?.click()}>
                          <Upload size={17} />{uploading ? '上传中' : '上传文件'}
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button disabled={!currentPath} onClick={() => {
                    const nextPath = pathParts.slice(0, -1).join('/');
                    setCurrentPath(nextPath);
                    loadFiles(selectedProjectId, nextPath);
                  }} className="rounded-lg border border-gray-200 p-2 text-gray-600 disabled:opacity-40">
                    <ChevronLeft size={18} />
                  </button>
                  <div className="min-w-0 flex-1 truncate text-sm text-gray-600">/{currentPath}</div>
                  <div className="relative w-full sm:w-64">
                    <Search className="absolute left-3 top-2.5 text-gray-400" size={17} />
                    <input className="input-field py-2 pl-9" value={searchTerm} onChange={event => setSearchTerm(event.target.value)} placeholder="搜索当前目录" />
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                    <tr><th className="px-5 py-3">名称</th><th className="px-5 py-3">版本</th><th className="px-5 py-3">大小</th><th className="px-5 py-3">协作状态</th><th className="px-5 py-3 text-right">操作</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredFiles.map(file => (
                      <tr key={file.id} className="hover:bg-gray-50">
                        <td className="px-5 py-4">
                          <button className="flex items-center gap-3 font-medium text-gray-900" onClick={() => file.is_directory ? (() => { setCurrentPath(file.relative_path); loadFiles(selectedProjectId, file.relative_path); })() : checkoutFile(file)}>
                            {file.is_directory ? <Folder className="text-amber-500" size={21} /> : <FileText className="text-brb-blue-600" size={21} />}
                            {file.name}
                          </button>
                        </td>
                        <td className="px-5 py-4 text-gray-600">{file.is_directory ? '—' : `v${file.current_version}`}</td>
                        <td className="px-5 py-4 text-gray-600">{file.is_directory ? '—' : `${Math.max(1, Math.ceil((file.size || 0) / 1024))} KB`}</td>
                        <td className="px-5 py-4">
                          {file.lock ? <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-700"><Lock size={13} />{file.lock.user_id === user?.id ? '我正在编辑' : `${file.lock.user_id} 已检出`}</span> : !file.is_directory && <span className="text-xs text-green-600">可检出</span>}
                        </td>
                        <td className="px-5 py-4">
                          {file.is_directory ? (
                            <div className="flex justify-end gap-1">
                              <button title="打开目录" onClick={() => { setCurrentPath(file.relative_path); loadFiles(selectedProjectId, file.relative_path); }} className="rounded px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">打开</button>
                              {canEdit && (confirmDeleteId === file.id ? (
                                <>
                                  <button disabled={deletingId === file.id} title="确认删除目录" onClick={() => deleteDirectory(file)} className="rounded px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60">{deletingId === file.id ? '删除中' : '确认删除'}</button>
                                  <button title="取消" onClick={() => setConfirmDeleteId('')} className="rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100">取消</button>
                                </>
                              ) : (
                                <button title="删除目录" onClick={() => setConfirmDeleteId(file.id)} className="rounded p-2 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={17} /></button>
                              ))}
                            </div>
                          ) : (
                            <div className="flex justify-end gap-1">
                              {!file.lock && <button title="打开" onClick={() => checkoutFile(file)} className="rounded px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">打开</button>}
                              {file.lock?.user_id === user?.id && <><button disabled={checkingInId === file.id} title="检入" onClick={() => checkinFile(file)} className="rounded px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-50">{checkingInId === file.id ? '检入中' : '检入'}</button><button title="取消检出" onClick={() => cancelCheckout(file)} className="rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50">取消检出</button></>}
                              <button title="版本历史" onClick={() => showVersions(file)} className="rounded p-2 text-gray-500 hover:bg-gray-100"><History size={17} /></button>
                              <button title="下载" onClick={() => downloadFile(file)} className="rounded p-2 text-gray-500 hover:bg-gray-100"><Download size={17} /></button>
                              {canEdit && (confirmDeleteId === file.id ? (
                                <>
                                  <button disabled={deletingId === file.id} title="确认删除" onClick={() => deleteFile(file)} className="rounded px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60">{deletingId === file.id ? '删除中' : '确认删除'}</button>
                                  <button title="取消" onClick={() => setConfirmDeleteId('')} className="rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100">取消</button>
                                </>
                              ) : (
                                <button title="删除" onClick={() => setConfirmDeleteId(file.id)} className="rounded p-2 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={17} /></button>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!loading && filteredFiles.length === 0 && <div className="py-20 text-center text-sm text-gray-400">当前目录暂无文件</div>}
              </div>
            </>
          ) : <div className="flex min-h-[620px] items-center justify-center text-gray-400">请选择或新建项目</div>}
        </main>
      </div>

      {historyFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setHistoryFile(null)}>
          <div className="card max-h-[80vh] w-full max-w-2xl overflow-auto p-6" onClick={event => event.stopPropagation()}>
            <div className="flex items-center justify-between"><h3 className="text-lg font-semibold">{historyFile.name} · 版本历史</h3><button onClick={() => setHistoryFile(null)} className="text-gray-500">关闭</button></div>
            <div className="mt-5 space-y-3">{versions.map(version => <div key={version.id} className="rounded-lg border border-gray-200 p-4"><div className="flex justify-between"><strong>v{version.version}</strong><span className="text-sm text-gray-500">{new Date(version.created_at).toLocaleString()}</span></div><div className="mt-2 text-xs text-gray-500">提交人：{version.created_by} · {(version.size / 1024).toFixed(1)} KB{version.from_history ? ` · 基于 v${version.base_version} 修订` : ''}</div><div className="mt-1 truncate font-mono text-xs text-gray-400">SHA-256: {version.content_hash || '旧版本未记录'}</div>{version.version !== historyFile.current_version && <div className="mt-3 flex justify-end gap-2"><button onClick={() => { const target = historyFile; setHistoryFile(null); checkoutFile(target, version.id); }} className="rounded px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50">打开编辑</button><button onClick={() => downloadVersion(version)} className="rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100">下载</button></div>}</div>)}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestFiles;
