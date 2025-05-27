import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/button';
import { cn } from '@/helpers/utils';

const Header: React.FC = () => {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 flex">
          <Link to="/" className="mr-6 flex items-center space-x-2 font-bold">
            <span className="hidden sm:inline-block">GenAgent Manager</span>
          </Link>
        </div>
        <nav className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
          <div className="flex-1 md:flex-initial">
            <div className="flex items-center gap-2">
              <Button asChild variant="ghost" size="sm">
                <Link to="/">Dashboard</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link to="/agents/new">Add Agent</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link to="/knowledge">Knowledge Base</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link to="/tools">Tools</Link>
              </Button>
            </div>
          </div>
        </nav>
      </div>
    </header>
  );
};

export default Header; 