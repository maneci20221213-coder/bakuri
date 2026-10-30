namespace Bakuri.Infrastructure;

/// <summary>Serial STA ownership keeps every Office/COM object and MuPDF document on its creating thread.</summary>
public sealed class StaRunner {
    readonly SemaphoreSlim gate=new(1,1);
    public async Task<T> Run<T>(Func<T> work,CancellationToken cancellation=default) {
        await gate.WaitAsync(cancellation).ConfigureAwait(false);
        try {
            var completion=new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
            var thread=new Thread(()=>{try{cancellation.ThrowIfCancellationRequested();completion.SetResult(work());}catch(OperationCanceledException){completion.TrySetCanceled(cancellation);}catch(Exception error){completion.SetException(error);}}){IsBackground=true,Name="Bakuri STA worker"};
            thread.SetApartmentState(ApartmentState.STA);thread.Start();return await completion.Task.ConfigureAwait(false);
        }finally{gate.Release();}
    }
}
