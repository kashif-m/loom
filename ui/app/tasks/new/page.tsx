'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import ErrorMessage from '../../../components/ErrorMessage';
import LoadingSpinner from '../../../components/LoadingSpinner';
import { submitTask } from '../../../lib/api';

export default function NewTask() {
  const router = useRouter();
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('normal');

  const mutation = useMutation({
    mutationFn: submitTask,
    onSuccess: (data) => {
      router.push(`/tasks/${data.task_id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (description.length >= 20) {
      mutation.mutate({ description, priority });
    }
  };

  const isValid = description.length >= 20 && description.length <= 2000;

  return (
    <div>
      <Navigation />
      
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader 
          title="Submit New Task" 
          subtitle="Describe what needs to be done"
        />

        {mutation.error && (
          <div className="mb-6">
            <ErrorMessage message="Failed to submit task. Please try again." />
          </div>
        )}

        <div className="bg-white shadow rounded-lg">
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            <div>
              <label 
                htmlFor="description" 
                className="block text-sm font-medium text-gray-700"
              >
                Description
              </label>
              <div className="mt-1">
                <textarea
                  id="description"
                  name="description"
                  rows={6}
                  className="shadow-sm focus:ring-amber-500 focus:border-amber-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  placeholder="Describe what needs to be done..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={mutation.isPending}
                />
              </div>
              <p className="mt-2 text-sm text-gray-500">
                {description.length} / 2000 characters
                {description.length > 0 && description.length < 20 && (
                  <span className="text-red-600 ml-2">Minimum 20 characters required</span>
                )}
              </p>
            </div>

            <div>
              <label 
                htmlFor="priority" 
                className="block text-sm font-medium text-gray-700"
              >
                Priority Hint (optional)
              </label>
              <select
                id="priority"
                name="priority"
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-amber-500 focus:border-amber-500 sm:text-sm rounded-md"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                disabled={mutation.isPending}
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="urgent">Urgent</option>
              </select>
              <p className="mt-2 text-sm text-gray-500">
                This is stored as metadata and does not affect routing
              </p>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={!isValid || mutation.isPending}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-amber-600 hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {mutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span className="ml-2">Routing your task...</span>
                  </>
                ) : (
                  'Submit Task'
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
