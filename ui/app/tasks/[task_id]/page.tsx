'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CheckCircle, Clock, FileText } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import StatusBadge from '../../../components/StatusBadge';
import LoadingSpinner from '../../../components/LoadingSpinner';
import ErrorMessage from '../../../components/ErrorMessage';
import { getTask, respondToEscalation, reassignTask } from '../../../lib/api';
import { formatDistanceToNow } from 'date-fns';

export default function TaskDetail() {
  const params = useParams();
  const taskId = params.task_id as string;
  const [responseText, setResponseText] = useState('');
  const [showTechnical, setShowTechnical] = useState(false);

  const { data: task, isLoading, error, refetch } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTask(taskId),
    refetchInterval: 15000, // Poll every 15 seconds
  });

  const respondMutation = useMutation({
    mutationFn: (message: string) => respondToEscalation(taskId, message),
    onSuccess: () => {
      setResponseText('');
      refetch();
    },
  });

  if (isLoading) {
    return (
      <div>
        <Navigation />
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        </main>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div>
        <Navigation />
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorMessage message="Failed to load task" />
          <div className="mt-4">
            <Link href="/tasks" className="text-amber-600 hover:text-amber-900">
              ← Back to tasks
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const isEscalated = task.status === 'escalated';
  const isClosed = task.status === 'closed';

  return (
    <div>
      <Navigation />
      
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link 
            href="/tasks" 
            className="text-sm text-amber-600 hover:text-amber-900 flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to tasks
          </Link>
        </div>

        <PageHeader title="Task Detail" />

        {/* Escalation Panel */}
        {isEscalated && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-start">
              <AlertTriangle className="h-6 w-6 text-red-400 mt-1" />
              <div className="ml-3 flex-1">
                <h3 className="text-lg font-medium text-red-800">
                  This task needs your input
                </h3>
                <p className="mt-2 text-sm text-red-700">
                  The agent encountered an issue and needs additional information or guidance.
                </p>
                
                <div className="mt-4">
                  <label className="block text-sm font-medium text-red-700">
                    Provide additional details or instructions
                  </label>
                  <textarea
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    rows={4}
                    className="mt-2 block w-full border-red-300 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 sm:text-sm"
                    placeholder="Describe what the agent should do..."
                  />
                  <div className="mt-3 flex gap-3">
                    <button
                      onClick={() => respondMutation.mutate(responseText)}
                      disabled={!responseText.trim() || respondMutation.isPending}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      {respondMutation.isPending ? 'Sending...' : 'Send response'}
                    </button>
                    <button
                      onClick={() => {/* TODO: reassign */}}
                      className="inline-flex items-center px-4 py-2 border border-red-300 text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 focus:outline-none"
                    >
                      Reassign to different team
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Task Header */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">{task.description}</h2>
                <p className="mt-1 text-sm text-gray-500 font-mono">{task.task_id}</p>
              </div>
              <StatusBadge status={task.status} />
            </div>
          </div>
          
          <div className="px-6 py-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Current State:</span>
              <span className="ml-2 font-medium">{task.current_state}</span>
            </div>
            <div>
              <span className="text-gray-500">Team:</span>
              <span className="ml-2 font-medium">{task.team_id}</span>
            </div>
            <div>
              <span className="text-gray-500">Assigned to:</span>
              <span className="ml-2 font-medium">{task.owner_agent_id}</span>
            </div>
            <div>
              <span className="text-gray-500">Created:</span>
              <span className="ml-2 font-medium">
                {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
              </span>
            </div>
          </div>
        </div>

        {/* Progress Timeline */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Progress Timeline</h3>
          </div>
          <div className="px-6 py-4">
            <div className="space-y-4">
              {task.history.map((h, idx) => (
                <div key={h.id} className="flex">
                  <div className="flex-shrink-0">
                    <div className="h-8 w-8 rounded-full bg-amber-100 flex items-center justify-center">
                      <CheckCircle className="h-4 w-4 text-amber-600" />
                    </div>
                  </div>
                  <div className="ml-4 flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      {h.from_state ? `${h.from_state} → ` : ''}{h.to_state}
                    </p>
                    <p className="text-xs text-gray-500">
                      by {h.agent_id} • {formatDistanceToNow(new Date(h.transitioned_at), { addSuffix: true })}
                    </p>
                  </div>
                </div>
              ))}
              {task.history.length === 0 && (
                <p className="text-sm text-gray-500">No state transitions yet</p>
              )}
            </div>
          </div>
        </div>

        {/* Technical Details */}
        <div className="bg-white shadow rounded-lg">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className="w-full px-6 py-4 flex items-center justify-between border-b border-gray-200 hover:bg-gray-50"
          >
            <span className="text-sm font-medium text-gray-900">Technical Details</span>
            <span className="text-gray-400">{showTechnical ? '▲' : '▼'}</span>
          </button>
          
          {showTechnical && (
            <div className="px-6 py-4">
              <pre className="text-xs text-gray-600 overflow-auto bg-gray-50 p-4 rounded">
                {JSON.stringify(task, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
