'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { FileText, Search } from 'lucide-react';
import Navigation from '../../components/Navigation';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import LoadingSpinner from '../../components/LoadingSpinner';
import ErrorMessage from '../../components/ErrorMessage';
import EmptyState from '../../components/EmptyState';
import { getTasks } from '../../lib/api';
import { Task } from '../../lib/types';
import { formatDistanceToNow } from 'date-fns';

const statusOptions = [
  { value: '', label: 'All Status' },
  { value: 'open', label: 'Open' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'escalated', label: 'Needs your input' },
  { value: 'closed', label: 'Closed' },
];

export default function TaskList() {
  const [status, setStatus] = useState('');
  const [teamId, setTeamId] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks', status, teamId],
    queryFn: () => getTasks(status || undefined, teamId || undefined),
  });

  const tasks = data?.tasks || [];

  // Sort escalated tasks to top
  const sortedTasks = [...tasks].sort((a, b) => {
    if (a.status === 'escalated' && b.status !== 'escalated') return -1;
    if (b.status === 'escalated' && a.status !== 'escalated') return 1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader 
          title="All Tasks" 
          subtitle="View and manage all tasks in the system"
        />

        {/* Filters */}
        <div className="mb-6 flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-amber-500 focus:border-amber-500 sm:text-sm rounded-md"
            >
              {statusOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Team
            </label>
            <input
              type="text"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder="Filter by team..."
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
            />
          </div>
        </div>

        {/* Tasks Table */}
        <div className="bg-white shadow rounded-lg">
          {isLoading ? (
            <div className="p-8 flex justify-center">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorMessage message="Failed to load tasks" />
            </div>
          ) : sortedTasks.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-12 w-12" />}
              title="No tasks found"
              description="Try adjusting your filters or submit a new task"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Task
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Team
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Assigned To
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedTasks.map((task: Task) => (
                    <tr key={task.task_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Link 
                          href={`/tasks/${task.task_id}`}
                          className="text-sm font-medium text-amber-600 hover:text-amber-900"
                        >
                          {task.description.substring(0, 60)}
                          {task.description.length > 60 ? '...' : ''}
                        </Link>
                        <div className="text-xs text-gray-500 mt-1 font-mono">
                          {task.task_id.substring(0, 8)}... | {task.current_state}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <StatusBadge status={task.status} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {task.team_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {task.owner_agent_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
