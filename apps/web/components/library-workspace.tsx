"use client";

import { useState } from "react";
import { BookOpen, Search, Headphones, Play, ChevronRight, FileText } from "lucide-react";

export function LibraryWorkspace() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAct, setSelectedAct] = useState<string | null>(null);

  // Mock data for the UI
  const acts = [
    { id: "contract", title: "The Indian Contract Act, 1872", sections: 266, type: "Central" },
    { id: "constitution", title: "The Constitution of India, 1950", sections: 395, type: "Central" },
    { id: "bns", title: "Bharatiya Nyaya Sanhita, 2023", sections: 358, type: "Central" },
  ];

  const sections = [
    { number: "73", title: "Compensation for loss or damage caused by breach of contract" },
    { number: "74", title: "Compensation for breach of contract where penalty stipulated for" },
    { number: "75", title: "Party rightfully rescinding contract, entitled to compensation" }
  ];

  return (
    <div className="flex h-full flex-col bg-gray-50/50 dark:bg-gray-900/50">
      <header className="flex h-14 items-center justify-between border-b px-6 bg-white dark:bg-gray-900">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-indigo-600" />
          <h1 className="text-lg font-semibold">Bare Acts Library</h1>
        </div>
        <div className="relative w-96">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-gray-500" />
          <input
            type="search"
            placeholder="Search acts, sections, or concepts..."
            className="h-9 w-full rounded-md border border-gray-300 pl-9 pr-4 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Acts List */}
        <div className="w-1/3 border-r bg-white dark:bg-gray-900 overflow-y-auto p-4">
          <h2 className="text-sm font-medium text-gray-500 mb-4 uppercase tracking-wider">Central Acts (1,000+)</h2>
          <div className="space-y-2">
            {acts.map((act) => (
              <div 
                key={act.id} 
                onClick={() => setSelectedAct(act.id)}
                className={`p-3 rounded-lg cursor-pointer border transition-colors ${
                  selectedAct === act.id 
                    ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20" 
                    : "border-gray-200 hover:border-indigo-300 dark:border-gray-800 dark:hover:border-gray-700"
                }`}
              >
                <div className="flex items-start justify-between">
                  <h3 className="font-medium text-sm leading-tight">{act.title}</h3>
                  <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                  <span className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">{act.type}</span>
                  <span>{act.sections} Sections</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main Content - Sections */}
        <div className="flex-1 bg-white dark:bg-gray-900 overflow-y-auto p-6">
          {!selectedAct ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-500">
              <BookOpen className="h-12 w-12 text-gray-300 mb-4" />
              <p>Select a Bare Act to view its sections</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto">
              <h2 className="text-2xl font-bold mb-6">The Indian Contract Act, 1872</h2>
              
              <div className="space-y-6">
                {sections.map((section) => (
                  <div key={section.number} className="border rounded-xl p-5 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="font-semibold text-lg text-indigo-700 dark:text-indigo-400">
                        Section {section.number}: {section.title}
                      </h3>
                      <button className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-sm px-3 py-1.5 rounded-full font-medium transition-colors">
                        <Headphones className="h-3.5 w-3.5 text-indigo-600" />
                        <span className="text-indigo-600 dark:text-indigo-400">Listen</span>
                      </button>
                    </div>
                    
                    <div className="prose dark:prose-invert text-sm text-gray-700 dark:text-gray-300 mb-4">
                      When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, compensation for any loss or damage caused to him thereby...
                    </div>
                    
                    <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2 text-amber-800 dark:text-amber-500 font-medium">
                        <FileText className="h-4 w-4" />
                        <span>KanoonGPT Simplified Explanation</span>
                      </div>
                      <p className="text-sm text-amber-900 dark:text-amber-200">
                        If someone breaks a contract, they have to pay the other person for the damage or loss they caused. However, this only applies to obvious damages that both people knew could happen when they signed the contract.
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
