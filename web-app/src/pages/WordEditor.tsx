import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Save, ArrowLeft } from 'lucide-react';
import './WordEditor.css';

declare global {
  interface Window {
    tinymce: any;
  }
}

const WordEditor: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const fileName = searchParams.get('file') || '';
  
  const editorRef = useRef<any>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [editorLoaded, setEditorLoaded] = useState(false);
  const [contentLoaded, setContentLoaded] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // 加载 TinyMCE
  useEffect(() => {
    console.log('开始加载 TinyMCE...');
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/tinymce@6.8.3/tinymce.min.js';
    script.async = true;
    script.onload = () => {
      console.log('TinyMCE 加载成功');
      setEditorLoaded(true);
    };
    script.onerror = () => {
      console.error('TinyMCE 加载失败');
      setError('编辑器加载失败，请刷新页面重试');
    };
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  // 加载 Word 文件
  useEffect(() => {
    if (fileName) {
      loadWordFile();
    }
  }, [fileName]);

  // 初始化编辑器
  useEffect(() => {
    console.log('状态检查:', { editorLoaded, contentLoaded, isInitialized });
    
    if (editorLoaded && contentLoaded && !isInitialized) {
      // 延迟初始化，确保 DOM 已更新
      setTimeout(() => {
        initEditor();
      }, 100);
    }
  }, [editorLoaded, contentLoaded, isInitialized]);

  const loadWordFile = async () => {
    console.log('开始加载 Word 文件...');
    
    try {
      const response = await fetch('/api/test-files/read-word', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ filepath: fileName }),
      });

      const result = await response.json();

      if (result.status === 'success') {
        console.log('Word 文件加载成功');
        setContent(result.content || '<p></p>');
        setContentLoaded(true);
      } else {
        throw new Error(result.message || '读取文件失败');
      }
    } catch (err) {
      console.error('加载Word文件失败:', err);
      setError(err instanceof Error ? err.message : '加载文件失败');
    }
  };

  const initEditor = () => {
    if (!window.tinymce) {
      console.error('TinyMCE 未加载');
      setError('编辑器未加载，请刷新页面重试');
      return;
    }

    // 检查 textarea 是否存在
    const textarea = document.getElementById('word-editor');
    if (!textarea) {
      console.error('textarea 元素不存在');
      setError('编辑器容器不存在，请刷新页面重试');
      return;
    }

    console.log('开始初始化 TinyMCE...');

    window.tinymce.init({
      selector: '#word-editor',
      menubar: true,
      language: 'zh_CN',
      language_url: 'https://cdn.jsdelivr.net/npm/tinymce-lang@6.8.3/langs6/zh_CN.js',
      plugins: [
        'advlist', 'autolink', 'lists', 'link', 'image', 'charmap',
        'print', 'preview', 'anchor', 'searchreplace', 'visualblocks',
        'code', 'fullscreen', 'insertdatetime', 'media', 'table',
        'paste', 'code', 'help', 'wordcount'
      ],
      toolbar: 'undo redo | formatselect | ' +
        'bold italic underline strikethrough | ' +
        'alignleft aligncenter alignright alignjustify | ' +
        'bullist numlist outdent indent | ' +
        'link image | ' +
        'table | ' +
        'removeformat | help',
      content_style: 'body { font-family: Microsoft YaHei, SimHei, Arial, sans-serif; font-size: 14px }',
      promotion: false,
      branding: false,
      resize: false,
      setup: (editor: any) => {
        editorRef.current = editor;
        editor.on('init', () => {
          console.log('TinyMCE 初始化成功');
          setIsInitialized(true);
        });
      }
    });
  };

  const handleSave = async () => {
    if (!editorRef.current) {
      alert('编辑器未初始化');
      return;
    }

    setSaving(true);
    try {
      const htmlContent = editorRef.current.getContent();
      
      const response = await fetch('/api/test-files/export-word', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filepath: fileName,
          content: htmlContent
        }),
      });

      const result = await response.json();

      if (result.status === 'success') {
        alert('文件保存成功');
      } else {
        throw new Error(result.message || '保存失败');
      }
    } catch (err) {
      console.error('保存文件失败:', err);
      alert(err instanceof Error ? err.message : '保存文件失败');
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    if (editorRef.current) {
      editorRef.current.destroy();
    }
    navigate(-1);
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 mb-4">{error}</div>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="word-editor-container">
      {/* 顶部工具栏 */}
      <div className="word-toolbar">
        <div className="flex items-center space-x-4">
          <button
            onClick={handleBack}
            className="flex items-center space-x-2 px-3 py-2 text-gray-600 hover:text-gray-800 transition-colors"
          >
            <ArrowLeft size={20} />
            <span>返回</span>
          </button>
          <div className="text-lg font-semibold text-gray-900">
            {fileName}
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !isInitialized}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          <Save size={18} />
          <span>{saving ? '保存中...' : '保存'}</span>
        </button>
      </div>

      {/* TinyMCE 编辑器 */}
      <div className="word-editor-content">
        {!isInitialized && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <div className="text-gray-600">初始化编辑器...</div>
            </div>
          </div>
        )}
        <textarea id="word-editor" defaultValue={content} style={{ display: isInitialized ? 'none' : 'block' }}></textarea>
      </div>
    </div>
  );
};

export default WordEditor;