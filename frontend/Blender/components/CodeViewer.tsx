import React, { useState } from 'react';
import { FILES } from '../constants';
import { ClipboardDocumentCheckIcon, ClipboardIcon } from '@heroicons/react/24/outline';

const CodeViewer: React.FC = () => {
  const [activeFile, setActiveFile] = useState(FILES[0]);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(activeFile.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full max-w-7xl mx-auto p-4 h-[calc(100vh-140px)] flex flex-col lg:flex-row gap-6">
      {/* File Explorer */}
      <div className="w-full lg:w-64 bg-cv-panel rounded-xl border border-gray-700 flex flex-col overflow-hidden shrink-0">
        <div className="p-4 bg-gray-800/50 border-b border-gray-700">
          <h3 className="font-bold text-gray-200">Project Files</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {FILES.map((file) => (
            <button
              key={file.filename}
              onClick={() => setActiveFile(file)}
              className={`w-full text-left px-4 py-3 rounded-lg text-sm font-mono transition-colors ${
                activeFile.filename === file.filename
                  ? 'bg-cv-accent/10 text-cv-accent border border-cv-accent/20'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
            >
              {file.filename}
            </button>
          ))}
        </div>
      </div>

      {/* Code Editor View */}
      <div className="flex-1 bg-cv-panel rounded-xl border border-gray-700 flex flex-col overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 bg-gray-800/50 border-b border-gray-700">
          <div className="flex items-center gap-3">
             <div className="flex gap-1.5">
               <div className="w-3 h-3 rounded-full bg-red-500"></div>
               <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
               <div className="w-3 h-3 rounded-full bg-green-500"></div>
             </div>
             <span className="text-gray-400 font-mono text-sm ml-2">{activeFile.filename}</span>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs font-medium transition-all"
          >
            {copied ? <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-400" /> : <ClipboardIcon className="w-4 h-4" />}
            {copied ? "COPIED" : "COPY RAW"}
          </button>
        </div>
        
        <div className="flex-1 overflow-auto bg-[#0d1117] p-6">
          <pre className="font-mono text-sm text-gray-300 leading-relaxed">
            <code>{activeFile.content}</code>
          </pre>
        </div>
      </div>
    </div>
  );
};

export default CodeViewer;