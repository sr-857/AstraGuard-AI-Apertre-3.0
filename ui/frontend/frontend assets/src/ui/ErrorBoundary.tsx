import React from 'react';
import { Component, PropsWithChildren } from 'react';

import styles from './ErrorBoundary.module.css';

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<PropsWithChildren, ErrorBoundaryState> {
    constructor(props: PropsWithChildren) {
        super(props);
        this.state = {
            hasError: false,
            error: null
        };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        console.error('Portfolio rendering error:', error);
        console.error('Component stack:', errorInfo.componentStack);

        // maybe send this to an error reporting service
    }

    handleRefresh = (): void => {
        window.location.reload();
    };

    handleStaticVersion = (): void => {
        window.location.href = '/templates/Portfolio.html';
    };

    handleConnectDeveloper = (): void => {
        window.location.href = '/templates/Portfolio.html#contact';
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className={styles.errorContainer}>
                    <div className={styles.stars}></div>
                    <div className={styles.errorContent}>
                        <div className={styles.icon}>
                            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M15 9L9 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M9 9L15 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>

                        <h2>Houston, we have a problem</h2>

                        <p className={styles.message}>
                            Something went wrong with the 3D experience.
                        </p>

                        <div className={styles.errorInfo}>
                            <div className={styles.errorCode}>
                                {this.state.error?.name || 'Error'}
                            </div>
                        </div>

                        <div className={styles.actions}>
                            <button
                                onClick={this.handleRefresh}
                                className={`${styles.button} ${styles.primary}`}
                            >
                                <span className={styles.buttonText}>
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.buttonIcon}>
                                        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                                        <path d="M3 3v5h5"></path>
                                    </svg>
                                    Retry
                                </span>
                            </button>

                            <button
                                onClick={this.handleStaticVersion}
                                className={`${styles.button} ${styles.secondary}`}
                            >
                                <span className={styles.buttonText}>
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.buttonIcon}>
                                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                        <line x1="3" y1="9" x2="21" y2="9"></line>
                                        <line x1="9" y1="21" x2="9" y2="9"></line>
                                    </svg>
                                    Static Version
                                </span>
                            </button>

                            <button
                                onClick={this.handleConnectDeveloper}
                                className={`${styles.button} ${styles.accent}`}
                            >
                                <span className={styles.buttonText}>
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.buttonIcon}>
                                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                                        <polyline points="22,6 12,13 2,6"></polyline>
                                    </svg>
                                    Connect with Developer
                                </span>
                            </button>
                        </div>

                        <div className={styles.tip}>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.tipIcon}>
                                <circle cx="12" cy="12" r="10"></circle>
                                <path d="M12 8v4"></path>
                                <path d="M12 16h.01"></path>
                            </svg>
                            <p>If the problem persists, try using the latest Chrome or Firefox.</p>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;